"""Reservation endpoints — candidate time recommendation."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.reservation_schema import (
    ReservationCandidateRequest,
    ReservationCandidateResponse,
    ReservationFromStoreRequest,
)
from backend.database.session import get_db
from backend.services.reservation_from_store_service import recommend_from_store
from backend.services.reservation_recommender import recommend_candidates

router = APIRouter(tags=["reservation"])


def _message(data) -> str:
    return (
        "예약 가능한 후보 시간을 찾았습니다."
        if data.recommended_candidates
        else "예약 가능한 시간이 없습니다."
    )


@router.post(
    "/reservations/candidates",
    response_model=ReservationCandidateResponse,
    summary="예약 후보 시간 추천 (rule-based)",
)
async def reservation_candidates(req: ReservationCandidateRequest):
    data = recommend_candidates(req)
    return success_response(message=_message(data), data=data.model_dump())


@router.post(
    "/reservations/candidates/from-store",
    response_model=ReservationCandidateResponse,
    summary="저장된 일정 기반 예약 후보 추천 (rule-based)",
)
def reservation_candidates_from_store(
    req: ReservationFromStoreRequest, db: Session = Depends(get_db)
):
    data = recommend_from_store(db, req)
    return success_response(message=_message(data), data=data.model_dump())
