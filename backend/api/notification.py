"""Stored-schedule notification plan endpoints.

Computes a departure/preparation plan from a SAVED schedule + user preferences.
The original /alerts/departure-plan (input-based) is unchanged. No push delivery.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.notification_schema import NotificationPlanRequest
from backend.database.schema.personalization_schema import (
    ReminderRecommendRequest,
    ReminderRecommendResponse,
)
from backend.services import reminder_recommender
from backend.database.session import get_db
from backend.services import notification_plan_service as service

router = APIRouter(tags=["notification"])


@router.post("/notifications/plan", summary="저장된 일정 기반 알림 계획 생성")
def create_plan(req: NotificationPlanRequest, db: Session = Depends(get_db)):
    try:
        data = service.build_plan(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return success_response(message="알림 계획을 생성했습니다.", data=data.model_dump())


@router.get("/notifications/plan/{schedule_id}", summary="저장된 일정 기반 알림 계획 조회")
def get_plan(
    schedule_id: str,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None),
    travel_minutes: Optional[int] = Query(None),
    buffer_minutes: Optional[int] = Query(None),
    weather: Optional[str] = Query(None),
    notification_preference: Optional[str] = Query(None),
    include_checklist: bool = Query(True),
    persist: bool = Query(False),
):
    req = NotificationPlanRequest(
        schedule_id=schedule_id, user_id=user_id, travel_minutes=travel_minutes,
        buffer_minutes=buffer_minutes, weather=weather,
        notification_preference=notification_preference,
        include_checklist=include_checklist, persist=persist,
    )
    try:
        data = service.build_plan(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return success_response(message="알림 계획을 생성했습니다.", data=data.model_dump())


@router.post(
    "/notifications/recommend",
    response_model=ReminderRecommendResponse,
    summary="개인 선호 반영 알림 추천 (기본 알림/출발 알림)",
)
def recommend_reminders(req: ReminderRecommendRequest, db: Session = Depends(get_db)):
    data = reminder_recommender.recommend_reminders(db, req)
    return success_response(message="알림 추천을 생성했습니다.", data=data.model_dump())
