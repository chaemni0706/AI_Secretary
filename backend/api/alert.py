"""Alert endpoints — departure & preparation planning.

Legacy request (context/user_preference) returns the original leave_time/
checklist/notifications payload. When options.include_travel_time is set, the
same endpoint returns the travel-aware `alert_plan` payload instead (additive;
legacy callers are unaffected).
"""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.alert_schema import (
    DeparturePlanRequest,
    DeparturePlanResponse,
)
from backend.services.departure_alert import (
    build_departure_plan,
    build_departure_plan_with_travel,
)

router = APIRouter(tags=["alert"])


@router.post(
    "/alerts/departure-plan",
    response_model=DeparturePlanResponse,
    summary="준비물·출발 알림 계획 생성 (rule-based; 이동 시간 옵션 지원)",
)
async def departure_plan(req: DeparturePlanRequest):
    # Travel-aware branch (additive): richer alert_plan shape.
    if req.options is not None and req.options.include_travel_time:
        data = build_departure_plan_with_travel(req)
        return success_response(
            message="알림 계획을 생성했습니다.",
            data=data.model_dump(),
        )

    # Legacy branch — unchanged behavior/response contract.
    data = build_departure_plan(req)
    return success_response(
        message="준비물 및 출발 알림 계획을 생성했습니다.",
        data=data.model_dump(),
    )
