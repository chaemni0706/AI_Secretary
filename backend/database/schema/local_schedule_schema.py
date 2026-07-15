"""Schedule (EVENT) request/response schemas.

API conventions (shared with Flutter): date 'YYYY-MM-DD', time 'HH:mm',
priority/status/source are lowercase. These map onto planner_items +
event_details via backend.services.planner_mapping.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    title: str
    date: str = Field(..., description="'YYYY-MM-DD'")
    # 하루 종일 일정은 start_time 없이 저장 가능(서버가 00:00 로 채우고 is_all_day=1).
    start_time: Optional[str] = Field(None, description="'HH:mm' (하루 종일이면 생략 가능)")
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    end_date: Optional[str] = Field(
        None, description="'YYYY-MM-DD' (기간 일정의 종료일. 생략하면 date와 동일)"
    )
    category: Optional[str] = None
    priority: str = "medium"
    location: Optional[str] = None
    memo: Optional[str] = None
    source: str = "user"
    is_all_day: bool = Field(False, description="하루 종일 일정 여부")
    travel_time_minutes: Optional[int] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "치과 예약",
                "date": "2026-07-03",
                "start_time": "14:00",
                "end_time": "15:00",
                "category": "hospital",
                "priority": "high",
                "location": "강남역 치과",
                "memo": "스케일링",
                "source": "user",
            }
        }
    )


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    location: Optional[str] = None
    memo: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    is_all_day: Optional[bool] = None
    travel_time_minutes: Optional[int] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "치과 재예약",
                "start_time": "15:00",
                "end_time": "16:00",
                "priority": "high",
            }
        }
    )


class ScheduleRead(BaseModel):
    id: str
    title: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    end_date: Optional[str] = None
    category: Optional[str] = None
    priority: str
    location: Optional[str] = None
    memo: Optional[str] = None
    status: str
    source: str
    is_all_day: bool = False
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule_draft": {
                    "title": "치과 예약",
                    "category": "hospital",
                    "date": "2026-07-03",
                    "start_time": "14:00",
                    "end_time": "15:00",
                    "location": "강남역 치과",
                    "priority": "high",
                    "source": "ai",
                },
                "intent": "create_schedule",
            }
        }
    )
