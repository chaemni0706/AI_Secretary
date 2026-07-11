"""Image verification endpoints."""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.response import success_response
from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationResponse,
    ReviewDecisionRequest,
    VerificationType,
    WakeupSessionCreateRequest,
)
from backend.services.image_verification_service import verify_image_upload
from backend.services.secondary_review_service import secondary_review_store
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
    # review_required(현재: water verified)면 secondary_review 큐에 pending 으로 등록하고 id 부여.
    # final_result enum/자동확정 흐름은 변경하지 않는다. exercise/study 등은 등록하지 않음.
    if data.review_required:
        review_id = secondary_review_store.register(data)
        data = data.model_copy(update={"verification_id": review_id})
    return success_response(
        message="인증사진 판정이 완료되었습니다.",
        data=data.model_dump(),
    )


@router.get(
    "/image-verifications/reviews/pending",
    summary="secondary_review 대기(pending) 목록 조회",
)
async def list_pending_reviews():
    items = [r.model_dump() for r in secondary_review_store.list_pending()]
    return success_response(message="검수 대기 목록입니다.", data=items)


@router.get(
    "/image-verifications/reviews/{verification_id}",
    summary="secondary_review 상세 조회",
)
async def get_review(verification_id: str):
    record = secondary_review_store.get(verification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="해당 검수 항목을 찾을 수 없습니다.")
    return success_response(message="검수 항목입니다.", data=record.model_dump())


@router.post(
    "/image-verifications/reviews/{verification_id}/decision",
    summary="secondary_review 결정 처리(approved/rejected/needs_retake)",
)
async def decide_review(verification_id: str, payload: ReviewDecisionRequest):
    try:
        record = secondary_review_store.decide(
            verification_id,
            decision=payload.decision,
            note=payload.note,
            reviewer_id=payload.reviewer_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="해당 검수 항목을 찾을 수 없습니다.")
    return success_response(message="검수 결정이 반영되었습니다.", data=record.model_dump())
