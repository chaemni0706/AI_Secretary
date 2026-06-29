"""Preparation / departure alert schemas (/api/v1/alerts)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AlertSchedule(BaseModel):
    title: str
    category: str = Field("etc", description="hospital | school | meeting | beauty | exercise | travel | etc")
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    location: Optional[str] = None


class AlertContext(BaseModel):
    weather: Optional[str] = Field(None, description="rain | snow | hot | cold | clear ...")
    estimated_travel_minutes: int = 0
    buffer_minutes: int = 0


class UserPreference(BaseModel):
    notification_style: str = Field("normal", description="normal | strong")
    forgetful: bool = False


class ChecklistItem(BaseModel):
    item: str
    reason: str


class NotificationItem(BaseModel):
    time: str = Field(..., description="'HH:mm'")
    message: str


class DeparturePlanRequest(BaseModel):
    schedule: AlertSchedule
    context: AlertContext = Field(default_factory=AlertContext)
    user_preference: UserPreference = Field(default_factory=UserPreference)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule": {
                    "title": "병원 예약",
                    "category": "hospital",
                    "date": "2026-06-30",
                    "start_time": "14:00",
                    "location": "서울OO병원",
                },
                "context": {
                    "weather": "rain",
                    "estimated_travel_minutes": 35,
                    "buffer_minutes": 10,
                },
                "user_preference": {"notification_style": "strong", "forgetful": True},
            }
        }
    )


class DeparturePlanData(BaseModel):
    leave_time: Optional[str] = Field(None, description="'HH:mm'")
    estimated_travel_minutes: int
    buffer_minutes: int
    checklist: List[ChecklistItem] = Field(default_factory=list)
    notifications: List[NotificationItem] = Field(default_factory=list)


class DeparturePlanResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[DeparturePlanData] = None
