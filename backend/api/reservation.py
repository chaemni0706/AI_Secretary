"""Reservation endpoints — candidate time recommendation.

Two families share this router:
  * the original rule-based recommender (constraints + existing_schedules), and
  * the mock virtual-business layer (category/date/time_preference -> candidates,
    business catalog lookups, and MVP booking into the local schedule store).
The two are independent; the original endpoints are unchanged.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.response import error_response, success_response
from backend.database.schema.reservation_message_schema import (
    FromCandidateRequest,
    FromCandidateResponse,
)
from backend.services.reservation_message_service import (
    MissingFieldsError,
    build_message_card,
)
from backend.database.schema.reservation_business_schema import (
    BusinessCandidateRequest,
    BusinessCandidateResponse,
    ReservationBookingRequest,
    ReservationBookingResponse,
)
from backend.database.schema.reservation_schema import (
    ReservationCandidateRequest,
    ReservationCandidateResponse,
    ReservationFromStoreRequest,
)
from backend.database.session import get_db
from backend.services import reservation_candidate_service as biz_reco
from backend.services import virtual_business_service as biz_service
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


# --------------------------------------------------------------------------- #
# Virtual-business layer (mock; no external reservation API)
# --------------------------------------------------------------------------- #
@router.post(
    "/reservations/business-candidates",
    response_model=BusinessCandidateResponse,
    summary="가상 업체 기반 예약 후보 추천 (mock)",
)
def reservation_business_candidates(
    req: BusinessCandidateRequest, db: Session = Depends(get_db)
):
    data = biz_reco.recommend_business_candidates(db, req)
    if data.candidates:
        message = "예약 가능한 후보 시간을 찾았습니다."
    elif data.alternatives:
        message = "조건에 맞는 예약 가능 시간이 없어 대체 시간대를 안내합니다."
    else:
        message = "조건에 맞는 예약 가능 시간이 없습니다."
    return success_response(message=message, data=data.model_dump())


@router.get("/reservations/businesses", summary="가상 업체 목록 조회 (mock)")
def list_businesses(category: Optional[str] = Query(None, description="카테고리 필터 (선택)")):
    items = biz_service.list_by_category(category) if category else biz_service.list_businesses()
    return success_response(
        message="가상 업체 목록입니다.",
        data=[b.model_dump() for b in items],
    )


@router.get("/reservations/businesses/{business_id}", summary="가상 업체 단건 조회 (mock)")
def get_business(business_id: str):
    business = biz_service.get_business(business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="업체를 찾을 수 없습니다.")
    return success_response(message="가상 업체 단건입니다.", data=business.model_dump())


@router.post(
    "/reservations/book",
    response_model=ReservationBookingResponse,
    summary="추천 후보를 내 로컬 일정으로 저장 (mock booking)",
)
def book_reservation(req: ReservationBookingRequest, db: Session = Depends(get_db)):
    try:
        schedule = biz_reco.book_reservation(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 예약 데이터입니다.")
    return success_response(
        message="예약 후보를 로컬 일정으로 저장했습니다.",
        data={"schedule": schedule.model_dump()},
    )


@router.post(
    "/reservations/message/from-candidate",
    response_model=FromCandidateResponse,
    summary="선택한 예약 후보로 예약 문의 메시지 생성 (draft-only)",
)
def reservation_message_from_candidate(req: FromCandidateRequest):
    try:
        data = build_message_card(req)
    except MissingFieldsError as exc:
        return error_response(
            message="예약 메시지 생성에 필요한 정보가 부족합니다.",
            status_code=422,
            data={"missing_fields": exc.missing},
        )
    label = {"inquiry": "예약 문의", "confirm": "예약 확정 요청", "change": "예약 변경 문의",
             "cancel": "예약 취소 요청", "check": "예약 확인 요청"}.get(req.action_type, "예약 문의")
    return success_response(message=f"{label} 메시지를 생성했습니다.", data=data.model_dump())
