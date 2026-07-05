"""통합 인증(verification) 도메인 엔드포인트.

기존 /image-verifications 엔드포인트는 그대로 유지하고(삭제 금지), 여기서는 water/exercise/study
(VLM 기반)와 wakeup(세션/시간 기반)을 하나의 도메인 경로 아래로 통합한다.

    POST /api/v1/verification/image/{verification_type}   # water | exercise | study
    POST /api/v1/verification/wakeup/session              # 세션 발급
    POST /api/v1/verification/wakeup/submit               # 기상 인증 이미지 제출

wakeup은 VLM/Rule Engine을 사용하지 않고 서버 수신 시각/세션/이미지 해시로 판정한다.
"""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.response import success_response
from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    WakeupSessionCreateRequest,
)
from backend.services import verification_orchestrator as orchestrator

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post(
    "/image/{verification_type}",
    summary="VLM 기반 이미지 인증 (water/exercise/study)",
)
async def verify_image_endpoint(
    verification_type: str,
    activity_type: Optional[ExerciseActivityType] = Form(None),
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    target_latitude: Optional[float] = Form(None),
    target_longitude: Optional[float] = Form(None),
    captured_at: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
):
    if not orchestrator.is_image_verification(verification_type):
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 인증 타입입니다: {verification_type} (water/exercise/study)",
        )
    if verification_type == "exercise" and activity_type is None:
        raise HTTPException(status_code=422, detail="exercise 인증에는 activity_type이 필요합니다.")
    try:
        data = orchestrator.verify_image(
            verification_type,
            file.file,
            file.filename or "",
            file.content_type,
            exercise_activity_type=activity_type,
            latitude=latitude,
            longitude=longitude,
            target_latitude=target_latitude,
            target_longitude=target_longitude,
            captured_at=captured_at,
            scheduled_at=scheduled_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return success_response(message="인증사진 판정이 완료되었습니다.", data=data.model_dump())


@router.post(
    "/wakeup/session",
    summary="기상 인증 세션 발급",
)
async def create_wakeup_session_endpoint(payload: WakeupSessionCreateRequest):
    try:
        data = orchestrator.create_wakeup_session(
            scheduled_at=payload.scheduled_at,
            allowed_early_minutes=payload.allowed_early_minutes,
            allowed_late_minutes=payload.allowed_late_minutes,
            session_ttl_seconds=payload.session_ttl_seconds,
            max_retries=payload.max_retries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return success_response(message="기상 인증 세션이 발급되었습니다.", data=data.model_dump())


@router.post(
    "/wakeup/submit",
    summary="기상 인증 이미지 제출 (서버 시각/세션 기반)",
)
async def submit_wakeup_endpoint(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    wakeup_data = orchestrator.verify_wakeup(
        session_id,
        file.file,
        file.filename or "",
        file.content_type,
    )
    return success_response(
        message="기상 인증 판정이 완료되었습니다.",
        data=orchestrator.build_wakeup_envelope(wakeup_data),
    )
