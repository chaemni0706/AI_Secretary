"""Reservation endpoints — candidate time recommendation."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.reservation_schema import (
    ReservationCandidateRequest,
    ReservationCandidateResponse,
)
from backend.services.reservation_recommender import recommend_candidates

router = APIRouter(tags=["reservation"])


@router.post(
    "/reservations/candidates",
    response_model=ReservationCandidateResponse,
    summary="예약 후보 시간 추천 (rule-based)",
)
async def reservation_candidates(req: ReservationCandidateRequest):
    data = recommend_candidates(req)
    message = (
        "예약 가능한 후보 시간을 찾았습니다."
        if data.recommended_candidates
        else "예약 가능한 시간이 없습니다."
    )
    return success_response(message=message, data=data.model_dump())
