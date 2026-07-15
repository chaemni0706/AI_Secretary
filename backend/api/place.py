"""Place recommendation endpoint — POST /api/v1/places/recommend.

Thin router: validate request -> call service -> return common envelope.
All logic lives in services/place_recommendation_service.py. External-API and
config failures are mapped to the project's {success, message, data} error
shape (never a raw 500).
"""

from fastapi import APIRouter

from backend.core.response import error_response, success_response
from backend.database.schema.place_schema import (
    PlaceRecommendRequest,
    PlaceRecommendResponse,
)
from backend.services import place_recommendation_service as svc
from backend.services.naver_place_client import NaverApiError, NaverConfigError

router = APIRouter(tags=["place"])


@router.post(
    "/places/recommend",
    response_model=PlaceRecommendResponse,
    summary="장소 추천 (네이버 지역 검색 기반, rule-based scoring)",
)
def recommend_places(req: PlaceRecommendRequest):
    try:
        data = svc.recommend_places(req.model_dump())
    except NaverConfigError as exc:
        # credentials missing/invalid — configuration problem, not a crash
        return error_response(message=str(exc), status_code=503)
    except NaverApiError as exc:
        # upstream Naver failure — degrade gracefully instead of 500
        return error_response(message=str(exc), status_code=502)

    message = (
        "추천 장소를 찾았습니다."
        if data.recommended_places
        else "조건에 맞는 추천 장소를 찾지 못했습니다."
    )
    return success_response(message=message, data=data.model_dump())
