"""Dashboard read endpoints (calendar + to-do aggregates).

GET-only, additive, backed by the existing local Schedule/To-do store.
Common envelope {success, message, data} preserved.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.session import get_db
from backend.services import dashboard_service as service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/today", summary="대시보드 - 특정 날짜 일정/할일 + 집계")
def dashboard_today(
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="'YYYY-MM-DD' (미지정 시 오늘)"),
    timezone: str = Query("Asia/Seoul"),
    current_datetime: Optional[str] = Query(None, description="ISO 8601 (next_schedule 계산 기준)"),
    user_id: Optional[str] = Query(None),
):
    data = service.get_today(db, date=date, current_datetime=current_datetime, user_id=user_id)
    return success_response(message="대시보드 데이터입니다.", data=data.model_dump())


@router.get("/dashboard/summary", summary="대시보드 - 요약 집계")
def dashboard_summary(
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="'YYYY-MM-DD' (미지정 시 오늘)"),
    timezone: str = Query("Asia/Seoul"),
    current_datetime: Optional[str] = Query(None, description="ISO 8601"),
    user_id: Optional[str] = Query(None),
):
    data = service.get_summary(db, date=date, current_datetime=current_datetime, user_id=user_id)
    return success_response(message="대시보드 요약입니다.", data=data.model_dump())
