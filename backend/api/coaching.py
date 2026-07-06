"""Life-coaching endpoint — rule-based emotion coaching connected to today's
schedule/todo, free time, personal preference, place and reservation hints.

NOT a medical diagnosis and NOT a new ML model. Common envelope preserved.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.life_coaching_schema import (
    LifeCoachingRequest,
    LifeCoachingResponse,
)
from backend.database.session import get_db
from backend.services import life_coaching_service

router = APIRouter(tags=["coaching"])


@router.post(
    "/coaching/life",
    response_model=LifeCoachingResponse,
    summary="감정 기반 생활 코칭 (rule-based, 비진단; 일정/빈시간/장소/예약 연계)",
)
def life_coaching(req: LifeCoachingRequest, db: Session = Depends(get_db)):
    data = life_coaching_service.coach(db, req)
    return success_response(message="생활 코칭 결과를 생성했습니다.", data=data.model_dump())
