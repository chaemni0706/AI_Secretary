"""Schedule (EVENT) request/response schemas.

API conventions (shared with Flutter): date 'YYYY-MM-DD', time 'HH:mm',
priority/status/source are lowercase. These map onto planner_items +
event_details via backend.services.planner_mapping.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    title: str
    date: str = Field(..., description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    category: Optional[str] = None
    priority: str = "medium"
    location: Optional[str] = None
    memo: Optional[str] = None
    source: str = "user"
    travel_time_minutes: Optional[int] = None


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    memo: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    travel_time_minutes: Optional[int] = None


class ScheduleRead(BaseModel):
    id: str
    title: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = None
    priority: str
    location: Optional[str] = None
    memo: Optional[str] = None
    status: str
    source: str
    travel_time_minutes: Optional[int] = None
    created_at: str
    updated_at: str


class ScheduleDraftInput(BaseModel):
    """Mirror of /ai/schedule/parse -> data.schedule_draft (paste-through)."""
    title: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: Optional[str] = Field(None, description="'HH:mm' (없으면 종일 일정)")
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    location: Optional[str] = None
    memo: Optional[str] = None
    priority: str = "medium"
    source: str = "ai"


class ScheduleFromDraftRequest(BaseModel):
    schedule_draft: ScheduleDraftInput
    intent: Optional[str] = Field(None, description="parse 응답의 intent (선택, 미사용 가능)")
