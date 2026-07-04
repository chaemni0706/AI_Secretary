"""Alert endpoints — departure & preparation planning."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.alert_schema import (
    DeparturePlanRequest,
    DeparturePlanResponse,
)
from backend.services.departure_alert import build_departure_plan

router = APIRouter(tags=["alert"])


@router.post(
    "/alerts/departure-plan",
    response_model=DeparturePlanResponse,
    summary="준비물·출발 알림 계획 생성 (rule-based)",
)
async def departure_plan(req: DeparturePlanRequest):
    data = build_departure_plan(req)
    return success_response(
        message="준비물 및 출발 알림 계획을 생성했습니다.",
        data=data.model_dump(),
    )
