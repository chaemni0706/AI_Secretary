"""Image verification endpoints."""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.response import success_response
from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationResponse,
    VerificationType,
    WakeupSessionCreateRequest,
)
from backend.services.image_verification_service import verify_image_upload
from backend.services.wakeup_verification_service import wakeup_session_store

router = APIRouter(tags=["image-verification"])


@router.post(
    "/image-verifications/wakeup/sessions",
    summary="기상 인증 세션 발급",
)
async def create_wakeup_session(payload: WakeupSessionCreateRequest):
    try:
        data = wakeup_session_store.create_session(
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
    "/image-verifications/wakeup/sessions/{session_id}/verify",
    summary="기상 인증 이미지 제출",
)
async def verify_wakeup_session(session_id: str, file: UploadFile = File(...)):
    data = wakeup_session_store.verify_upload(
        session_id=session_id,
        file_obj=file.file,
        filename=file.filename or "",
        content_type=file.content_type,
    )
    return success_response(message="기상 인증 판정이 완료되었습니다.", data=data.model_dump())


@router.post(
    "/image-verifications",
    response_model=ImageVerificationResponse,
    summary="인증사진 업로드 및 룰 기반 판정",
)
async def verify_image(
    verification_type: VerificationType = Form(...),
    activity_type: Optional[ExerciseActivityType] = Form(None),
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    target_latitude: Optional[float] = Form(None),
    target_longitude: Optional[float] = Form(None),
    captured_at: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
):
    if verification_type == "exercise" and activity_type is None:
        raise HTTPException(status_code=422, detail="exercise 인증에는 activity_type이 필요합니다.")
    try:
        data = verify_image_upload(
            file.file,
            filename=file.filename or "",
            content_type=file.content_type,
            verification_type=verification_type,
            latitude=latitude,
            longitude=longitude,
            target_latitude=target_latitude,
            target_longitude=target_longitude,
            captured_at=captured_at,
            scheduled_at=scheduled_at,
            exercise_activity_type=activity_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return success_response(
        message="인증사진 판정이 완료되었습니다.",
        data=data.model_dump(),
    )
