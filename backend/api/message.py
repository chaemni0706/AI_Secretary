"""Message endpoints — reservation inquiry message generation."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.message_schema import (
    ReservationMessageRequest,
    ReservationMessageResponse,
)
from backend.services.message_generator import generate_message

router = APIRouter(tags=["message"])


@router.post(
    "/messages/reservation",
    response_model=ReservationMessageResponse,
    summary="예약 문의 메시지 생성 (template + LLM fallback)",
)
async def reservation_message(req: ReservationMessageRequest):
    data = generate_message(req)
    return success_response(
        message="예약 문의 메시지를 생성했습니다.",
        data=data.model_dump(),
    )
