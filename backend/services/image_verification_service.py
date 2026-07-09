"""Image verification orchestration service."""

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
)
from backend.services.image_verification_rule_engine import evaluate_image_verification
from backend.services.image_verification_rules_loader import allowed_labels
from backend.services.vision_analyzer import (
    VisionAnalyzer,
    get_default_vision_analyzer,
    get_study_fallback_analyzer,
)

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# study 1차 결과가 아래 상태이면 fallback(Qwen 등) 재판정을 시도한다.
# (증거 부족/불확실/품질 계열 — 소형 모델 study 병목 보완용. 최종 판정은 여전히 Rule Engine.)
_STUDY_FALLBACK_TRIGGER_CODES = frozenset(
    {"quality_unusable", "study_pattern_missing", "study_priority:uncertain_screen_content"}
)


# study verified 는 강한 근거 2개(종이+화면 조합 또는 강한 positive)가 필요하다. 1차(소형 모델)에서
# 근거가 이보다 적어 통과하지 못하면, study 정확도가 높은 fallback(Qwen)으로 재확인한다.
_STUDY_MIN_EVIDENCE_FOR_VERIFY = 2


def _analyze(vision, image_path, verification_type, labels, exercise_activity_type):
    """analyzer 가 activity-aware(analyze_with_context) 를 지원하면 activity 를 전달한다.

    exercise 정규화기는 activity 를 알아야 환경 근거(gym_environment/home_workout_environment)를
    보강한다. Mock/OpenAI analyzer 는 기존 analyze(3-arg) 그대로 사용(인터페이스 무변경).
    """
    fn = getattr(vision, "analyze_with_context", None)
    if callable(fn):
        return fn(image_path, verification_type, labels, exercise_activity_type)
    return vision.analyze(image_path, verification_type, labels)


def _should_study_fallback(result, analysis) -> bool:
    """study 1차 결과에 대해 fallback 재판정이 필요한지.

    FP 안전: fallback 은 verified 를 우회하지 않고 상위 모델로 다시 evidence 를 뽑아
    Rule Engine 이 재판정할 뿐이다(Qwen study FP=0). 통과된 건은 건드리지 않는다.
    """
    if result.result == "verified":
        return False  # 이미 통과면 fallback 불필요
    if not analysis.study_visual_evidence:
        return True  # 학습 근거가 전혀 없음 → 상위 모델로 재확인
    codes = {ev.code for ev in result.rule_evidence}
    if result.result == "retake_required" and bool(codes & _STUDY_FALLBACK_TRIGGER_CODES):
        return True
    # 근거가 verify 기준(2개)보다 적어 통과 못한 경우도 상위 모델로 재확인(예: handwritten_notes 1개만 추출).
    if result.result in {"retake_required", "rejected"} and \
            len(analysis.study_visual_evidence) < _STUDY_MIN_EVIDENCE_FOR_VERIFY:
        return True
    return False


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
    study_fallback_analyzer: Optional[VisionAnalyzer] = None,
) -> ImageVerificationData:
    if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("지원하지 않는 이미지 형식입니다.")

    # analyzer 를 명시 주입하지 않은 경우(=프로덕션 기본 경로)에만 provider/fallback 을 자동 선택한다.
    # (테스트가 MockVisionAnalyzer 를 주입하면 fallback 을 건드리지 않아 기존 동작 유지.)
    use_defaults = analyzer is None

    tmp_path = _save_temp_upload(file_obj, filename)
    try:
        _validate_image_file(tmp_path)
        labels = allowed_labels(verification_type)
        vision = analyzer or get_default_vision_analyzer()
        analysis = _analyze(vision, tmp_path, verification_type, labels, exercise_activity_type)
        context = _build_context(
            latitude,
            longitude,
            target_latitude,
            target_longitude,
            captured_at,
            scheduled_at,
            exercise_activity_type,
        )
        result = evaluate_image_verification(verification_type, analysis, context)

        # study fallback: 1차 근거가 부족/불확실하면 상위 모델(Qwen 등)로 재판정한다.
        # VLM→VisionAnalysis→Rule Engine 구조를 그대로 한 번 더 수행할 뿐, 판정 주체는 Rule Engine.
        if verification_type == "study" and use_defaults:
            fallback = study_fallback_analyzer or get_study_fallback_analyzer()
            if (
                fallback is not None
                and getattr(fallback, "available", lambda: True)()
                and _should_study_fallback(result, analysis)
            ):
                fb_analysis = _analyze(fallback, tmp_path, verification_type, labels,
                                       exercise_activity_type)
                if fb_analysis.quality.usable:
                    result = evaluate_image_verification(
                        verification_type, fb_analysis, context
                    )
        return result
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
