"""Briefing endpoints — daily schedule/to-do briefing."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.briefing_schema import (
    DailyBriefingRequest,
    DailyBriefingResponse,
)
from backend.services.briefing_generator import generate_briefing

router = APIRouter(tags=["briefing"])


@router.post(
    "/briefings/daily",
    response_model=DailyBriefingResponse,
    summary="하루 브리핑 생성 (rule-based)",
)
async def daily_briefing(req: DailyBriefingRequest):
    data = generate_briefing(req)
    return success_response(
        message="하루 브리핑을 생성했습니다.",
        data=data.model_dump(),
    )
