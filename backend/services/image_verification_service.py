"""Image verification orchestration service.

Production pipeline (all 3 VLM tasks -- water/exercise/study -- share this
exact contract, per this task's requirement #4):

    Camera image + task
      -> on-device/server Smol evidence (get_default_vision_analyzer)
      -> Rule Engine (evaluate_image_verification) on Smol evidence alone
      -> routing decision:
           - genuine image-quality failure -> stop, retake_required
           - Smol found an explicit strong blocker -> stop, that result stands
           - otherwise (positive / weak / uncertain / parser failure /
             model unloaded / inference error / missing evidence / mixed
             scene) -> ALWAYS escalate to Qwen7B (get_qwen7b_analyzer),
             even if Smol alone looked "verified" -- Smol never verifies
             alone in this pipeline.
      -> Qwen7B full-image evidence extraction (its own internal Parser;
         see qwen_evidence_parser.py) on the ORIGINAL image
      -> evidence merge (Smol ∪ Qwen7B; a blocker found by either source is
         never dropped)
      -> Rule Engine (evaluate_image_verification) on merged evidence --
         the ONLY place a decision is made
      -> backend FP guard (image_verification_fp_guard.py) -- may only
         downgrade verified -> retake_required on explicit contradictory
         evidence; never a decision-maker
      -> secondary_review policy (water only; evidence/uncertainty-based,
         not a blanket per-task rule -- see apply_secondary_review_policy)
      -> final ImageVerificationData, with engine_used/fallback_reason/
         guard_reason always populated (never silently blank on failure)

Backward-compat note: passing `analyzer=` explicitly (as existing tests
that want a single fixed analyzer already do) skips this whole routing --
matches the pre-existing "explicit injection = test controls everything"
convention documented below in `verify_image_upload`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional

from PIL import Image, UnidentifiedImageError

from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationContext,
    ImageVerificationData,
    LocationInput,
    TimeContext,
    VerificationType,
    VisionAnalysis,
)
from backend.services.image_verification_fp_guard import apply_fp_guard
from backend.services.image_verification_rule_engine import evaluate_image_verification
from backend.services.image_verification_rules_loader import allowed_labels
from backend.services.qwen7b_vision_analyzer import get_qwen7b_analyzer
from backend.services.vision_analyzer import (
    VisionAnalyzer,
    get_default_vision_analyzer,
)

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

_TASK_EVIDENCE_FIELD = {
    "water": "water_visual_evidence",
    "study": "study_visual_evidence",
    "exercise": "exercise_visual_evidence",
}

# Explicit, confident-negative RuleEvidence codes -- matches
# image_verification_rule_engine.py::_priority_result exactly (not new
# values). When Smol's own first pass hits one of these, there is no value
# in an extra Qwen7B call: the blocker already stands.
_STRONG_BLOCKER_CODES = {
    "water": {"water_priority:empty_container", "water_priority:non_water_beverage"},
    "study": {"study_priority:gaming_content", "study_priority:entertainment_video",
              "study_priority:social_media", "study_priority:shopping_content",
              "study_priority:non_study_screen"},
    "exercise": {"exercise_priority:unrelated_environment", "exercise_priority:wrong_activity_environment"},
}

# Substrings that mark a `quality.issues` entry as an INFRASTRUCTURE failure
# (model not loaded / crashed / unparseable output) rather than a genuine
# photo-quality problem. Only infra failures escalate past the "quality
# gate" -- a real bad photo (blur/dark/resolution) still stops immediately,
# since re-asking a different model cannot fix the photo itself.
_INFRA_FAILURE_MARKERS = (
    "is not loaded", "failed to load", "inference error", "could not be parsed",
    "analysis failed", "returned no analysis", "returned no evidence",
)

_REVIEW_TASKS = frozenset({"water"})


def _is_infra_failure(analysis: VisionAnalysis) -> bool:
    if analysis.quality.usable:
        return False
    return any(marker in issue for issue in analysis.quality.issues for marker in _INFRA_FAILURE_MARKERS)


def _smol_fallback_reason(analysis: VisionAnalysis) -> str:
    """Classifies WHY Smol's result didn't stand on its own, distinctly --
    Phase 11.C: previously every escalation was mislabeled
    'smol_not_confident_alone' even when Smol was actually unavailable, had a
    parser failure, or hit an inference error. Each category is now reported
    honestly, checked against the same issue-text markers `_is_infra_failure`
    already uses (not new heuristics)."""
    issues_blob = " ".join(analysis.quality.issues)
    if not analysis.quality.usable:
        if "could not be parsed" in issues_blob:
            return "smol_parser_failure"
        if "is not loaded" in issues_blob or "failed to load" in issues_blob:
            return "smol_unavailable"
        if "inference error" in issues_blob or "analysis failed" in issues_blob:
            return "smol_inference_error"
    return "smol_not_confident_alone"


def apply_secondary_review_policy(data: ImageVerificationData) -> ImageVerificationData:
    """verified(water)를 evidence/uncertainty 기반으로만 review 로 보낸다.

    이전 정책(모든 water verified를 무조건 review_required=True)은 제거되었다.
    명확한 positive evidence(container + filled_container/clear_liquid, 등)로
    모델 스스로 uncertainty="low" 를 보고했다면 그대로 verified 로 확정된다.
    모델이 스스로 확신하지 못한 경우(uncertainty != "low")에만 review 로 보낸다 --
    Rule Engine core 는 여전히 미수정, orchestrator layer 정책만 바뀐 것.
    """
    if data.result != "verified" or data.verification_type not in _REVIEW_TASKS:
        return data
    if data.vlm_analysis.uncertainty != "low":
        return data.model_copy(update={
            "review_required": True,
            "review_reason": f"water_model_uncertainty:{data.vlm_analysis.uncertainty}",
        })
    return data


def _analyze(vision, image_path, verification_type, labels, exercise_activity_type):
    fn = getattr(vision, "analyze_with_context", None)
    if callable(fn):
        return fn(image_path, verification_type, labels, exercise_activity_type)
    return vision.analyze(image_path, verification_type, labels)


def _smol_immediate_stop(task: str, smol_result: ImageVerificationData) -> tuple[bool, str]:
    """True when Smol's own result should stand without any Qwen7B call:
    a genuine (non-infra) quality failure, or an explicit strong blocker."""
    codes = {ev.code for ev in smol_result.rule_evidence}
    if "quality_unusable" in codes and not _is_infra_failure(smol_result.vlm_analysis):
        return True, "smol_quality_unusable"
    if smol_result.result != "verified":
        hit = codes & _STRONG_BLOCKER_CODES.get(task, set())
        if hit:
            return True, f"smol_strong_blocker:{sorted(hit)}"
    return False, ""


def _merge_evidence(task: str, smol_analysis: VisionAnalysis, qwen_analysis: VisionAnalysis) -> VisionAnalysis:
    """Union positive/blocker evidence from both sources. A blocker found by
    either source is kept (never dropped by the other source's silence).
    Qwen7B's own quality/uncertainty/scene_complexity win (higher-fidelity
    full-image pass), but nothing from Smol's evidence is discarded."""
    field = _TASK_EVIDENCE_FIELD[task]
    merged_task_evidence = sorted(set(getattr(smol_analysis, field, None) or []) |
                                   set(getattr(qwen_analysis, field, None) or []))
    merged_blockers = sorted(set(smol_analysis.blockers or []) | set(qwen_analysis.blockers or []))

    objects_by_label = {o.label: o for o in smol_analysis.objects}
    for o in qwen_analysis.objects:
        objects_by_label[o.label] = o  # qwen's observation wins on conflict

    payload = {
        "quality": qwen_analysis.quality if qwen_analysis.quality.usable else smol_analysis.quality,
        "scene": qwen_analysis.scene or smol_analysis.scene,
        "objects": list(objects_by_label.values()),
        "visible_text": sorted(set(smol_analysis.visible_text) | set(qwen_analysis.visible_text)),
        "visual_evidence": sorted(set(smol_analysis.visual_evidence) | set(qwen_analysis.visual_evidence)),
        field: merged_task_evidence,
        "blockers": merged_blockers,
        "uncertainty": qwen_analysis.uncertainty,
        "scene_complexity": qwen_analysis.scene_complexity,
        "model_name": f"smol+{qwen_analysis.model_name}" if qwen_analysis.model_name else "smol",
        "parser_version": qwen_analysis.parser_version,
        "parser_status": qwen_analysis.parser_status,
    }
    return VisionAnalysis(**payload)


def _log_routing(stage: str, **fields) -> None:
    """Always-on routing log so engine/fallback/rule/guard/parser status are
    never hidden -- requirement: visible in logs, including on failure."""
    kv = " ".join(f"{k}={v!r}" for k, v in fields.items())
    print(f"[image_verification] stage={stage} {kv}")


def verify_image_upload(
    file_obj: BinaryIO,
    filename: str,
    content_type: Optional[str],
    verification_type: VerificationType,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    target_latitude: Optional[float] = None,
    target_longitude: Optional[float] = None,
    captured_at: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    exercise_activity_type: Optional[ExerciseActivityType] = None,
    analyzer: Optional[VisionAnalyzer] = None,
    fallback_analyzer: Optional[VisionAnalyzer] = None,
    study_fallback_analyzer: Optional[VisionAnalyzer] = None,  # deprecated alias, kept for backward compat
) -> ImageVerificationData:
    if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("지원하지 않는 이미지 형식입니다.")

    # analyzer 를 명시 주입하면(=단일 analyzer 로 테스트를 완전히 제어하고 싶은 경우) 전체 라우팅을
    # 건너뛰고 기존처럼 1회 평가만 한다. 프로덕션 기본 경로(analyzer=None)만 Smol->Qwen7B 라우팅을 탄다.
    use_defaults = analyzer is None
    fallback_override = fallback_analyzer or study_fallback_analyzer

    tmp_path = _save_temp_upload(file_obj, filename)
    try:
        _validate_image_file(tmp_path)
        labels = allowed_labels(verification_type)
        context = _build_context(latitude, longitude, target_latitude, target_longitude,
                                  captured_at, scheduled_at, exercise_activity_type)

        if not use_defaults:
            analysis = _analyze(analyzer, tmp_path, verification_type, labels, exercise_activity_type)
            result = evaluate_image_verification(verification_type, analysis, context)
            result = result.model_copy(update={"engine_used": "analyzer_injected", "fallback_reason": ""})
            return apply_fp_guard(verification_type, apply_secondary_review_policy(result))

        # --- production routing (Smol -> [Qwen7B] -> merge -> Rule Engine -> guard) ---
        smol = get_default_vision_analyzer()
        smol_analysis = _analyze(smol, tmp_path, verification_type, labels, exercise_activity_type)
        smol_result = evaluate_image_verification(verification_type, smol_analysis, context)
        _log_routing("smol", task=verification_type, result=smol_result.result,
                     codes=[e.code for e in smol_result.rule_evidence],
                     quality_usable=smol_analysis.quality.usable, issues=smol_analysis.quality.issues)

        stop, stop_reason = _smol_immediate_stop(verification_type, smol_result)
        if stop:
            final = smol_result.model_copy(update={"engine_used": f"smol_only:{stop_reason}",
                                                     "fallback_reason": "not_needed:" + stop_reason})
            final = apply_fp_guard(verification_type, apply_secondary_review_policy(final))
            _log_routing("final", task=verification_type, engine=final.engine_used,
                         result=final.result, guard=final.guard_reason)
            return final

        escalation_reason = _smol_fallback_reason(smol_analysis)
        qwen = fallback_override or get_qwen7b_analyzer()
        qwen_analysis = _analyze(qwen, tmp_path, verification_type, labels, exercise_activity_type)
        _log_routing("qwen7b", task=verification_type, quality_usable=qwen_analysis.quality.usable,
                     issues=qwen_analysis.quality.issues, parser_status=qwen_analysis.parser_status,
                     model_name=qwen_analysis.model_name)

        if not qwen_analysis.quality.usable:
            # Smol was not a strong blocker (weak/positive/uncertain) AND Qwen7B could not confirm
            # (unloaded/inference error/parse failure after repair) -> fail safe. Never verified
            # from Smol alone, per this task's explicit prohibition.
            fail_safe = smol_result.model_copy(update={
                "result": "retake_required",
                "engine_used": "fail_safe:qwen7b_unavailable",
                "fallback_reason": f"{escalation_reason};qwen7b_unavailable_or_failed:{qwen_analysis.quality.issues}",
            })
            _log_routing("final", task=verification_type, engine=fail_safe.engine_used,
                         result=fail_safe.result)
            return fail_safe

        merged = _merge_evidence(verification_type, smol_analysis, qwen_analysis)
        merged_result = evaluate_image_verification(verification_type, merged, context)
        merged_result = merged_result.model_copy(update={
            "engine_used": "smol_plus_qwen7b",
            "fallback_reason": escalation_reason,
        })
        final = apply_fp_guard(verification_type, apply_secondary_review_policy(merged_result))
        _log_routing("final", task=verification_type, engine=final.engine_used, result=final.result,
                     rule_reason=[e.code for e in final.rule_evidence], guard=final.guard_reason,
                     parser_status=merged.parser_status)
        return final
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _save_temp_upload(file_obj: BinaryIO, filename: str) -> Path:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".img"

    fd, raw_path = tempfile.mkstemp(prefix="image-verification-", suffix=suffix)
    path = Path(raw_path)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise ValueError("이미지 파일은 10MB 이하만 업로드할 수 있습니다.")
                out.write(chunk)
        if size == 0:
            raise ValueError("빈 이미지 파일입니다.")
        return path
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _validate_image_file(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("유효한 이미지 파일이 아닙니다.") from exc


def _build_context(
    latitude: Optional[float],
    longitude: Optional[float],
    target_latitude: Optional[float],
    target_longitude: Optional[float],
    captured_at: Optional[str],
    scheduled_at: Optional[str],
    exercise_activity_type: Optional[ExerciseActivityType] = None,
) -> ImageVerificationContext:
    location = None
    if latitude is not None and longitude is not None:
        location = LocationInput(latitude=latitude, longitude=longitude)
    target_location = None
    if target_latitude is not None and target_longitude is not None:
        target_location = LocationInput(latitude=target_latitude, longitude=target_longitude)
    return ImageVerificationContext(
        location=location,
        target_location=target_location,
        time=TimeContext(captured_at=captured_at, scheduled_at=scheduled_at),
        exercise_activity_type=exercise_activity_type,
    )
