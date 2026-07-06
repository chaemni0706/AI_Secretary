"""Daily briefing schemas (/api/v1/briefings)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BriefingSchedule(BaseModel):
    title: str
    category: str = Field("etc", description="hospital | school | meeting | ...")
    start_time: Optional[str] = Field(None, description="'HH:mm'")
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    priority: str = Field("medium", description="high | medium | low")


class BriefingTodo(BaseModel):
    title: str
    priority: str = Field("medium", description="high | medium | low")
    is_done: bool = False


class PriorityOrderItem(BaseModel):
    title: str
    priority: str
    reason: str


class DailyBriefingRequest(BaseModel):
    date: str = Field(..., description="Target day 'YYYY-MM-DD'")
    schedules: List[BriefingSchedule] = Field(default_factory=list)
    todos: List[BriefingTodo] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-06-30",
                "schedules": [
                    {"title": "오전 수업", "category": "school", "start_time": "09:00",
                     "end_time": "12:00", "priority": "medium"},
                    {"title": "병원 예약", "category": "hospital", "start_time": "14:00",
                     "end_time": "15:00", "priority": "high"},
                    {"title": "팀플 회의", "category": "meeting", "start_time": "19:00",
                     "end_time": "20:00", "priority": "high"},
                ],
                "todos": [
                    {"title": "진료카드 챙기기", "priority": "high", "is_done": False}
                ],
            }
        }
    )


class DailyBriefingData(BaseModel):
    summary: str
    key_points: List[str] = Field(default_factory=list)
    priority_order: List[PriorityOrderItem] = Field(default_factory=list)
    tts_text: Optional[str] = Field(
        None,
        description="assistant_tone/response_length/nudge_strength 반영 TTS 문장(일정 개수·최우선 일정 기반, rule-based). additive.",
    )


class DailyBriefingResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[DailyBriefingData] = None
