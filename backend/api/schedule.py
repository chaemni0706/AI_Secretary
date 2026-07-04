"""Schedule endpoints — AI natural-language schedule parsing.

Endpoints:
  * /ai/schedule/parse           — original rule-based parser (unchanged).
  * /ai/schedule/parse/enhanced  — LLM-first + rule fallback + hybrid merge,
                                   returning a flat payload with parse_source,
                                   warnings, timezone/base_date and clarification.
  * /ai/schedule/confirm         — persist a user-approved parse as a local
                                   schedule (reuses local_schedule_service).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.schedule_parse_schema import (
    EnhancedParseRequest,
    EnhancedParseResponse,
    ScheduleConfirmRequest,
    ScheduleConfirmResponse,
)
from backend.database.schema.schedule_schema import (
    ScheduleParseRequest,
    ScheduleParseResponse,
)
from backend.database.session import get_db
from backend.services.schedule_parse_service import (
    confirm_schedule,
    confirm_todo,
    parse_enhanced,
    resolve_item_type,
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


@router.post(
    "/ai/schedule/parse/enhanced",
    response_model=EnhancedParseResponse,
    summary="자연어 일정 파싱 (LLM 우선 + 룰 fallback + hybrid)",
)
async def parse_schedule_enhanced_endpoint(req: EnhancedParseRequest):
    data, message = parse_enhanced(req)
    return success_response(message=message, data=data.model_dump())


@router.post(
    "/ai/schedule/confirm",
    response_model=ScheduleConfirmResponse,
    summary="파싱 결과를 로컬 일정으로 저장 (confirm)",
)
def confirm_schedule_endpoint(req: ScheduleConfirmRequest, db: Session = Depends(get_db)):
    """Persist a user-approved parse. Branches on item_type (EVENT | TODO) so the
    same endpoint serves both flows; returns data.schedule or data.todo."""
    try:
        item_type = resolve_item_type(req)
        if item_type == "TODO":
            todo = confirm_todo(db, req)
            return success_response(
                message="할 일을 저장했습니다.",
                data={"todo": todo.model_dump()},
            )
        schedule = confirm_schedule(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 일정 데이터입니다.")
    return success_response(
        message="일정을 저장했습니다.",
        data={"schedule": schedule.model_dump()},
    )
