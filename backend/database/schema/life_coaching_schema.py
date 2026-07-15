"""Life-coaching schemas (/api/v1/coaching/life).

Rule-based emotion coaching CONNECTED to today's schedule/todo, free time,
personal preference, place and reservation suggestions. NOT a medical diagnosis
and NOT a new ML model — a Flutter-card-friendly aggregation over existing
services. All fields are structured for card UIs.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.personalization_schema import Personalization


class LifeCoachingRequest(BaseModel):
    user_id: str = "local-user"
    text: str = Field(..., min_length=1, description="감정/상태 입력")
    date: Optional[str] = Field(None, description="'YYYY-MM-DD' (없으면 timezone 기준 오늘)")
    timezone: str = "Asia/Seoul"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user",
                "text": "오늘 너무 지치고 머리가 복잡해",
                "date": "2026-07-01",
                "timezone": "Asia/Seoul",
            }
        }
    )


class NextSchedule(BaseModel):
    title: str
    start_time: Optional[str] = None


class DueTodo(BaseModel):
    title: str
    due_date: Optional[str] = None


class ContextSummary(BaseModel):
    date: str
    schedule_count: int = 0
    todo_count: int = 0
    next_schedule: Optional[NextSchedule] = None
    due_todos: List[DueTodo] = Field(default_factory=list)


class CoachingCard(BaseModel):
    action_type: str = Field(..., description="rest | reschedule | break_down_task | start_small | prepare_now | find_free_time | recommend_place | recommend_reservation | encourage")
    title: str
    message: str
    reason: str


class FreeTimeSlot(BaseModel):
    date: str
    start_time: str
    end_time: str
    recommended_activity: str = "휴식"
    reason: str


class PlaceRecommendation(BaseModel):
    place_type: str
    name: str
    reason: str


class ReservationSuggestion(BaseModel):
    category: str
    time_preference: str = "afternoon"
    reason: str
    next_api: str = "POST /api/v1/reservations/business-candidates"


class SafetyInfo(BaseModel):
    diagnosis: bool = False
    medical_advice: bool = False
    risk_level: str = "low"       # low | high
    note: str = "이 코칭은 의료 진단이 아니라 생활 관리 제안입니다."
    support_message: Optional[str] = None


class LifeCoachingData(BaseModel):
    input_text: str
    primary_emotion: str
    secondary_emotions: List[str] = Field(default_factory=list)
    emotion_score: float = 0.5
    context_summary: ContextSummary
    coaching_cards: List[CoachingCard] = Field(default_factory=list)
    free_time_slots: List[FreeTimeSlot] = Field(default_factory=list)
    place_recommendations: List[PlaceRecommendation] = Field(default_factory=list)
    reservation_suggestions: List[ReservationSuggestion] = Field(default_factory=list)
    personalization: Personalization = Field(default_factory=Personalization)
    safety: SafetyInfo = Field(default_factory=SafetyInfo)
    warnings: List[str] = Field(default_factory=list)


class LifeCoachingResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[LifeCoachingData] = None
