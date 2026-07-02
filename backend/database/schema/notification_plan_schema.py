"""MVP notification-plan schemas (plan-only; NOT real OS push).

A `reminder_plan` bundles reminders + a preparation checklist + personalization
metadata + a `delivery` block that makes the plan-only nature explicit
(`os_push_enabled=false`, `status="planned_only"`). Reused by schedule/todo
confirm responses and the plan lookup endpoint. All additive; no DB change.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from backend.database.schema.personalization_schema import Personalization


class ReminderEntry(BaseModel):
    type: str = Field(..., description="default | departure | deadline")
    minutes_before: Optional[int] = Field(None, description="일정 시작(또는 마감) 기준 분. deadline은 null 가능")
    trigger_time: Optional[str] = Field(None, description="'YYYY-MM-DDTHH:MM:SS' (시간 없으면 null)")
    message: str
    reason: str


class ChecklistEntry(BaseModel):
    item: str
    reason: str


class DeliveryInfo(BaseModel):
    os_push_enabled: bool = False
    status: str = "planned_only"
    note: str = "MVP에서는 실제 OS 푸시가 아니라 알림 계획만 생성합니다."


class ReminderPlan(BaseModel):
    reminders: List[ReminderEntry] = Field(default_factory=list)
    checklist: List[ChecklistEntry] = Field(default_factory=list)
    personalization: Personalization = Field(default_factory=Personalization)
    delivery: DeliveryInfo = Field(default_factory=DeliveryInfo)
    warnings: List[str] = Field(default_factory=list)


class NotificationPlanView(BaseModel):
    """GET /notifications/plans/{item_id} response data."""

    item_id: str
    item_type: str = Field(..., description="EVENT | TODO")
    title: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    due_date: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    reminder_plan: ReminderPlan


class NotificationPlanResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[NotificationPlanView] = None
