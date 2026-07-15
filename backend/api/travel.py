"""Travel endpoint — POST /api/v1/travel/estimate.

Thin router: validate -> travel_time_service -> common envelope. Maps config /
upstream failures map to the shared error shape (never a raw 500).
"""

from fastapi import APIRouter

from backend.core.response import error_response, success_response
from backend.database.schema.travel_schema import (
    TravelEstimateRequest,
    TravelEstimateResponse,
)
from backend.services import travel_time_service as svc
from backend.services.naver_maps_client import NaverMapsApiError, NaverMapsConfigError

router = APIRouter(tags=["travel"])


@router.post(
    "/travel/estimate",
    response_model=TravelEstimateResponse,
    summary="목적지까지 거리·예상 이동 시간 계산 (네이버 Maps)",
)
def estimate(req: TravelEstimateRequest):
    try:
        data = svc.estimate_travel(
            origin=req.origin.model_dump(),
            destination=req.destination.model_dump(),
            transport_mode=req.transport_mode,
        )
    except NaverMapsConfigError as exc:
        return error_response(message=str(exc), status_code=503)
    except NaverMapsApiError as exc:
        return error_response(message=str(exc), status_code=502)
    except ValueError as exc:
        return error_response(message=str(exc), status_code=422)

    return success_response(message="이동 시간을 계산했습니다.", data=data)


