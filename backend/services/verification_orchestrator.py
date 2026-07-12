"""Verification orchestrator — 인증 타입을 적절한 판정 로직으로 라우팅한다.

인증 타입은 두 범주로 나뉜다:

1. VLM 기반 이미지 인증 (water / exercise / study)
   - 이미지 → VisionAnalyzer → VisionAnalysis → evaluate_image_verification(type, ...) → 판정
   - 기존 image verification pipeline(verify_image_upload)을 그대로 사용한다.

2. 세션/시간 기반 인증 (wakeup)
   - Qwen VLM이나 Rule Engine을 사용하지 않는다.
   - 서버 수신 시각, 인증 세션, 이미지 SHA256 중복 검사, 재촬영 횟수로 판정한다.
   - 기존 wakeup_verification_service를 그대로 사용한다.

이 모듈은 라우팅/책임 분리만 담당하며 기존 서비스의 판정 로직을 바꾸지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, BinaryIO, Optional

from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationData,
    VerificationType,
    WakeupSessionData,
    WakeupVerificationData,
)
from backend.services.image_verification_service import verify_image_upload
from backend.services.vision_analyzer import VisionAnalyzer
from backend.services.wakeup_verification_service import wakeup_session_store

# VLM 기반 이미지 인증 타입
# wake_up = 기상 상황(사람+아침 맥락) **이미지** 인증. 시간/세션 기반 wakeup 과 별개(얼굴/신원 식별 아님).
IMAGE_VERIFICATION_TYPES: frozenset[str] = frozenset({"water", "exercise", "study", "wake_up"})
# 세션/시간 기반 인증 타입 (VLM 미사용)
SESSION_VERIFICATION_TYPES: frozenset[str] = frozenset({"wakeup"})
SUPPORTED_VERIFICATION_TYPES: frozenset[str] = IMAGE_VERIFICATION_TYPES | SESSION_VERIFICATION_TYPES


class UnsupportedVerificationType(ValueError):
    """지원하지 않는 verification_type."""


def verification_category(verification_type: str) -> str:
    """'image' | 'session'. 알 수 없으면 UnsupportedVerificationType."""
    if verification_type in IMAGE_VERIFICATION_TYPES:
        return "image"
    if verification_type in SESSION_VERIFICATION_TYPES:
        return "session"
    raise UnsupportedVerificationType(f"지원하지 않는 verification_type입니다: {verification_type}")


def is_image_verification(verification_type: str) -> bool:
    return verification_type in IMAGE_VERIFICATION_TYPES


def is_session_verification(verification_type: str) -> bool:
    return verification_type in SESSION_VERIFICATION_TYPES


# ---------------------------------------------------------------------------
# VLM 기반 이미지 인증 (water / exercise / study)
# ---------------------------------------------------------------------------

def verify_image(
    verification_type: str,
    file_obj: BinaryIO,
    filename: str,
    content_type: Optional[str],
    *,
    exercise_activity_type: Optional[ExerciseActivityType] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    target_latitude: Optional[float] = None,
    target_longitude: Optional[float] = None,
    captured_at: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    analyzer: Optional[VisionAnalyzer] = None,
) -> ImageVerificationData:
    """water/exercise/study 이미지 인증. 기존 pipeline(verify_image_upload)에 위임."""
    if verification_type not in IMAGE_VERIFICATION_TYPES:
        raise UnsupportedVerificationType(
            f"이미지 인증이 아닌 타입입니다: {verification_type}"
        )
    if verification_type == "exercise" and exercise_activity_type is None:
        raise ValueError("exercise 인증에는 activity_type이 필요합니다.")

    return verify_image_upload(
        file_obj,
        filename=filename,
        content_type=content_type,
        verification_type=verification_type,  # type: ignore[arg-type]
        latitude=latitude,
        longitude=longitude,
        target_latitude=target_latitude,
        target_longitude=target_longitude,
        captured_at=captured_at,
        scheduled_at=scheduled_at,
        exercise_activity_type=exercise_activity_type,
        analyzer=analyzer,
    )


# ---------------------------------------------------------------------------
# 세션/시간 기반 인증 (wakeup) — VLM/Rule Engine 미사용
# ---------------------------------------------------------------------------

def create_wakeup_session(
    scheduled_at: str,
    allowed_early_minutes: int = 5,
    allowed_late_minutes: int = 10,
    session_ttl_seconds: int = 120,
    max_retries: int = 2,
    now: Optional[datetime] = None,
) -> WakeupSessionData:
    return wakeup_session_store.create_session(
        scheduled_at=scheduled_at,
        allowed_early_minutes=allowed_early_minutes,
        allowed_late_minutes=allowed_late_minutes,
        session_ttl_seconds=session_ttl_seconds,
        max_retries=max_retries,
        now=now,
    )


def verify_wakeup(
    session_id: str,
    file_obj: BinaryIO,
    filename: str,
    content_type: Optional[str],
    now: Optional[datetime] = None,
) -> WakeupVerificationData:
    """기상 인증. 서버 수신 시각/세션/이미지 해시 기반. VLM/Rule Engine을 호출하지 않는다."""
    return wakeup_session_store.verify_upload(
        session_id=session_id,
        file_obj=file_obj,
        filename=filename,
        content_type=content_type,
        now=now,
    )


# ---------------------------------------------------------------------------
# 공통 진입점 (단일 인터페이스)
# ---------------------------------------------------------------------------

def verify(verification_type: str, **kwargs: Any):
    """verification_type에 따라 알맞은 인증 로직으로 라우팅하는 단일 진입점.

    - image 타입(water/exercise/study): ImageVerificationData 반환
    - session 타입(wakeup): WakeupVerificationData 반환 (session_id 필요)
    - 그 외: UnsupportedVerificationType
    """
    category = verification_category(verification_type)  # 알 수 없으면 여기서 예외

    if category == "image":
        return verify_image(
            verification_type,
            kwargs.get("file_obj"),
            kwargs.get("filename", ""),
            kwargs.get("content_type"),
            exercise_activity_type=kwargs.get("exercise_activity_type"),
            latitude=kwargs.get("latitude"),
            longitude=kwargs.get("longitude"),
            target_latitude=kwargs.get("target_latitude"),
            target_longitude=kwargs.get("target_longitude"),
            captured_at=kwargs.get("captured_at"),
            scheduled_at=kwargs.get("scheduled_at"),
            analyzer=kwargs.get("analyzer"),
        )

    # session (wakeup)
    session_id = kwargs.get("session_id")
    if not session_id:
        raise ValueError("wakeup 인증에는 session_id가 필요합니다.")
    return verify_wakeup(
        session_id,
        kwargs.get("file_obj"),
        kwargs.get("filename", ""),
        kwargs.get("content_type"),
        now=kwargs.get("now"),
    )


def build_wakeup_envelope(data: WakeupVerificationData) -> dict:
    """wakeup 결과를 공통 response 형태(verification_type/result/wakeup_data)로 감싼다."""
    return {
        "verification_type": "wakeup",
        "result": data.decision,
        "wakeup_data": data.model_dump(),
    }
