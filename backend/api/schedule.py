"""Schedule endpoints — AI natural-language schedule parsing."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.schedule_schema import (
    ScheduleParseRequest,
    ScheduleParseResponse,
)
from backend.services.schedule_parser import parse_schedule

router = APIRouter(tags=["schedule"])


@router.post(
    "/ai/schedule/parse",
    response_model=ScheduleParseResponse,
    summary="자연어에서 일정 정보 추출 (rule-based)",
)
async def parse_schedule_endpoint(req: ScheduleParseRequest):
    data = parse_schedule(req)
    return success_response(
        message="일정 정보를 추출했습니다.",
        data=data.model_dump(),
    )
