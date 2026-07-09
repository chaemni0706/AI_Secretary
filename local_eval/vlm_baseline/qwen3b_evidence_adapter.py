"""Qwen-3B EVIDENCE ADAPTER → EXISTING Rule Engine.

Qwen evidence(친숙 토큰) → 기존 Rule Engine 이 기대하는 VisionAnalysis evidence schema 로 변환하고,
**기존 evaluate_image_verification(Rule Engine core, 미수정)** 을 호출해 final_result 를 받는다.
Qwen 은 final_result 를 확정하지 않는다. 최종 판정 = 기존 Rule Engine.

pipeline:
  evidence = qwen3b_evidence_engine.extract(image_path, task)        # Qwen evidence
  rule_input = to_existing_rule_input(evidence, task)                # → VisionAnalysis schema
  data = run_existing_rule_engine(rule_input)                        # 기존 Rule Engine
  → final_result / rule_reason / rule_trace  (기존 시스템 호환 output)
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # repo root (…/AI_Secretary_FeatureJW_Qwen)
for p in (str(_ROOT), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import qwen3b_evidence_engine as engine  # noqa: E402

# ---- 기존 Rule Engine / schema import (core 미수정, read-only) ----
try:
    from backend.database.schema.image_verification_schema import (  # noqa: E402
        VisionAnalysis, ImageVerificationContext,
    )
    from backend.services.image_verification_rule_engine import (  # noqa: E402
        evaluate_image_verification,
    )
    _RULE_ENGINE_AVAILABLE = True
    _RULE_ENGINE_IMPORT_ERROR = ""
except Exception as _exc:  # 기존 Rule Engine 위치/의존성 문제 시 최소 fallback
    _RULE_ENGINE_AVAILABLE = False
    _RULE_ENGINE_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"

# ---------------------------------------------------------------------------
# Qwen evidence 토큰 → 기존 Rule Engine schema evidence 코드 매핑
# ---------------------------------------------------------------------------
_WATER_POS = {"visible_water": "visible_water", "clear_liquid_visible": "visible_clear_liquid",
              "waterline_visible": "visible_water"}
_WATER_CONTAINER = {"transparent_container", "cup_visible", "bottle_visible"}
_WATER_BLOCK = {"empty_cup": "empty_container", "empty_bottle": "empty_container",
                "colored_beverage": "non_water_beverage", "coffee": "non_water_beverage",
                "juice": "non_water_beverage", "milk": "non_water_beverage", "tea": "non_water_beverage",
                "soda": "non_water_beverage", "opaque_container": "opaque_closed_container",
                "liquid_unclear": "uncertain_liquid"}
_STUDY_POS = {"open_book": "open_textbook", "textbook": "open_textbook", "notes": "handwritten_notes",
              "writing_or_solving": "problem_solving_material", "study_document": "educational_document",
              "code_screen": "code_editor", "lecture_material": "lecture_video",
              "study_related_text": "study_content_on_screen"}
_STUDY_BLOCK = {"game": "gaming_content", "youtube": "entertainment_video", "video": "entertainment_video",
                "movie": "entertainment_video", "shopping": "shopping_content", "sns": "social_media",
                "empty_desk": "closed_study_materials", "laptop_only": "non_study_screen",
                "closed_book_only": "closed_study_materials", "screen_unclear": "uncertain_screen_content"}
# Qwen 운동 positive → (기존 Rule Engine 이 요구하는) activity-consistent 코드 묶음.
# 기존 exercise 규칙은 context.exercise_activity_type + 해당 activity 의 core 근거(자세/기구/환경)를 함께 요구.
_EX_POS = {
    "active_exercise_pose": ["home_exercise_pose_visible", "home_workout_environment"],
    "person_exercising": ["home_exercise_pose_visible", "home_workout_environment"],
    "workout_action": ["home_exercise_pose_visible", "home_workout_environment"],
    "stretching": ["home_exercise_pose_visible", "home_workout_environment"],
    "yoga_pose": ["yoga_pose_visible", "yoga_environment"],
    "lifting_weight": ["exercise_pose_visible", "dumbbell_present"],
    "person_using_equipment": ["exercise_pose_visible", "exercise_equipment_present", "gym_environment"],
}
_EX_BLOCK = {"equipment_only": "exercise_equipment_present", "gym_background_only": "gym_environment",
             "workout_clothes_only": "unrelated_environment", "sitting": "insufficient_exercise_evidence",
             "resting": "insufficient_exercise_evidence", "selfie": "unrelated_environment",
             "folded_mat": "insufficient_exercise_evidence", "pose_unclear": "uncertain_exercise_environment"}
_UNCERTAIN_CODE = {"water": "uncertain_liquid", "study": "uncertain_screen_content",
                   "exercise": "uncertain_exercise_environment"}


def _map(task, ev):
    """returns (schema_codes, objects, has_positive). blocker priority + uncertainty→uncertain code."""
    pos_tokens = [str(x) for x in (ev.get("positive_evidence") or [])]
    block_tokens = [str(x) for x in (ev.get("blockers") or [])] + [str(x) for x in (ev.get("negative_evidence") or [])]
    unc = str(ev.get("uncertainty", "high")).lower()
    codes, objs, has_pos = [], [], False
    if task == "water":
        for t in pos_tokens:
            if t in _WATER_POS: codes.append(_WATER_POS[t]); has_pos = True
        if any(t in _WATER_CONTAINER for t in pos_tokens):
            if has_pos: codes.append("filled_container")
            objs.append({"label": "water_bottle" if "bottle_visible" in pos_tokens else "cup", "confidence": 0.6})
        for t in block_tokens:
            if t in _WATER_BLOCK: codes.append(_WATER_BLOCK[t])
    elif task == "study":
        for t in pos_tokens:
            if t in _STUDY_POS: codes.append(_STUDY_POS[t]); has_pos = True
        for t in block_tokens:
            if t in _STUDY_BLOCK: codes.append(_STUDY_BLOCK[t])
        if has_pos: objs.append({"label": "book", "confidence": 0.6})
    elif task == "exercise":
        for t in pos_tokens:
            if t in _EX_POS:
                codes.extend(_EX_POS[t]); has_pos = True
        for t in block_tokens:
            if t in _EX_BLOCK: codes.append(_EX_BLOCK[t])
    # uncertainty high → 기존 FP=0 정책 반영: uncertain 코드 추가(최종 판정은 Rule Engine).
    if unc == "high":
        codes.append(_UNCERTAIN_CODE[task])
    # dedupe, 순서 보존
    seen, out = set(), []
    for c in codes:
        if c not in seen: seen.add(c); out.append(c)
    return out, objs, has_pos


def _derive_exercise_activity(codes):
    """emitted exercise 코드 → context.exercise_activity_type (기존 규칙 요구). 기본 gym."""
    s = set(codes)
    if s & {"yoga_pose_visible", "yoga_environment", "yoga_mat_present", "yoga_studio_present"}:
        return "yoga"
    if s & {"home_exercise_pose_visible", "home_workout_environment", "exercise_mat_present", "resistance_band_present"}:
        return "home_workout"
    if s & {"running_environment", "treadmill_present", "treadmill_running_environment", "running_track_present"}:
        return "running"
    if s & {"swimming_pool_environment", "swimming_lane_present"}:
        return "swimming"
    if s & {"pilates_environment", "pilates_reformer_present", "pilates_equipment_present"}:
        return "pilates"
    return "gym"


def to_existing_rule_input(evidence_result, task):
    """Qwen evidence → 기존 Rule Engine 입력(VisionAnalysis + context + verification_type)."""
    ev = evidence_result["evidence"] if "evidence" in evidence_result else evidence_result
    codes, objs, has_pos = _map(task, ev)
    iq = str(ev.get("image_quality", "unknown")).lower()
    usable = iq not in ("poor", "unusable")
    va_dict = {
        "quality": {"brightness": "normal", "blur": "low" if usable else "high", "usable": usable, "issues": []},
        "scene": ev.get("scene_type") or None,
        "objects": objs,
        "visible_text": [],
        "study_visual_evidence": codes if task == "study" else [],
        "water_visual_evidence": codes if task == "water" else [],
        "exercise_visual_evidence": codes if task == "exercise" else [],
    }
    ctx = {}
    if task == "exercise" and has_pos:
        ctx = {"exercise_activity_type": _derive_exercise_activity(codes)}
    return {"verification_type": task, "analysis": va_dict, "context": ctx, "mapped_codes": codes}


def run_existing_rule_engine(rule_input):
    """기존 evaluate_image_verification 호출(core 미수정). Rule Engine 없으면 TODO fallback."""
    task = rule_input["verification_type"]
    if not _RULE_ENGINE_AVAILABLE:
        # TODO: 기존 Rule Engine 연결 지점. import 실패 시 보수적 minimal fallback(FP=0: 기본 retake).
        codes = rule_input.get("mapped_codes", [])
        return {"result": "retake_required", "score": 0, "mandatory_passed": False,
                "rule_reason": f"rule_engine_unavailable({_RULE_ENGINE_IMPORT_ERROR}); minimal fallback",
                "rule_trace": codes, "_fallback": True}
    va = VisionAnalysis(**rule_input["analysis"])
    ctx = ImageVerificationContext(**(rule_input.get("context") or {}))
    data = evaluate_image_verification(task, va, ctx)
    return {"result": data.result, "score": data.score, "mandatory_passed": data.mandatory_passed,
            "rule_reason": (data.rule_evidence[0].message if data.rule_evidence else ""),
            "rule_trace": [e.code for e in data.rule_evidence], "_fallback": False}


def verify(image_path, task, model_path=None, mock_output=None):
    """전체 파이프라인 → 기존 시스템 호환 output. final_result 는 기존 Rule Engine 산출."""
    er = engine.extract(image_path, task, mock_output=mock_output) if model_path is None \
        else engine.extract(image_path, task, model_path=model_path, mock_output=mock_output)
    ev = er["evidence"]
    rule_input = to_existing_rule_input(er, task)
    rule_out = run_existing_rule_engine(rule_input)
    return {
        "task": task,
        "final_result": rule_out["result"],           # ← 앱이 사용할 값(기존 Rule Engine 산출)
        "rule_reason": rule_out["rule_reason"],
        "rule_trace": rule_out["rule_trace"],
        "evidence": {
            "positive_evidence": ev.get("positive_evidence", []),
            "negative_evidence": ev.get("negative_evidence", []),
            "blockers": ev.get("blockers", []),
            "uncertainty": ev.get("uncertainty", "high"),
            "image_quality": ev.get("image_quality", "unknown"),
            "visible_objects": ev.get("visible_objects", []),
            "visible_actions": ev.get("visible_actions", []),
            "mapped_rule_codes": rule_input["mapped_codes"],
        },
        "debug": {  # 앱이 사용하면 안 되는 값
            "engine": "qwen3b",
            "qwen_raw_output": er["qwen_raw_output"],
            "qwen_parse_status": er["qwen_parse_status"],
            "rule_engine_fallback": rule_out.get("_fallback", False),
        },
    }
