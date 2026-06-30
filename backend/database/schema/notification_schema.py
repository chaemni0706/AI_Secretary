"""Stored-schedule notification plan schemas.

Builds on the existing alert (departure_plan) shapes — ChecklistItem /
NotificationItem are reused so the contract matches /alerts/departure-plan.
Computes a plan only; no push delivery.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from backend.database.schema.alert_schema import ChecklistItem, NotificationItem


class NotificationPlanRequest(BaseModel):
    schedule_id: str
    user_id: Optional[str] = None
    travel_minutes: Optional[int] = Field(None, description="요청값 우선")
    buffer_minutes: Optional[int] = Field(None, description="요청값 우선")
    weather: Optional[str] = Field(None, description="rain | snow | hot | cold ...")
    notification_preference: Optional[str] = Field(
        None, description="normal | strong | forgetful | late_prone (요청값 우선)"
    )
    include_checklist: bool = True
    persist: bool = Field(False, description="True면 계산된 알림을 reminders 테이블에 저장")


class NotificationPlanData(BaseModel):
    schedule_id: str
    user_id: Optional[str] = None
    leave_time: Optional[str] = None
    checklist: List[ChecklistItem] = Field(default_factory=list)
    notifications: List[NotificationItem] = Field(default_factory=list)
    source: str = "stored_schedule"
    applied_preference: str = "normal"
    applied_travel_minutes: int = 0
    applied_buffer_minutes: int = 0
    persisted_reminders: int = 0
