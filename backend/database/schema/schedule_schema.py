"""Schedule natural-language parsing schemas (/api/v1/schedule)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.common_schema import InputType, Priority, Source


class ScheduleParseRequest(BaseModel):
    input: str = Field(..., description="Raw user utterance to analyze")
    input_type: InputType = InputType.text
    current_datetime: Optional[str] = Field(
        None, description="Caller's current datetime, ISO 8601 (used to resolve '내일' etc.)"
    )
    timezone: str = "Asia/Seoul"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input": "내일 오후 2시에 병원 예약 잡아줘",
                "input_type": "text",
                "current_datetime": "2026-06-29T10:00:00+09:00",
                "timezone": "Asia/Seoul",
            }
        }
    )


class ScheduleSlots(BaseModel):
    title: Optional[str] = None
    date_expression: Optional[str] = Field(None, description="Raw date phrase, e.g. '내일'")
    time_expression: Optional[str] = Field(None, description="Raw time phrase, e.g. '오후 2시'")
    date: Optional[str] = Field(None, description="Resolved date 'YYYY-MM-DD'")
    start_time: Optional[str] = Field(None, description="'HH:mm'")
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    category: Optional[str] = None
    location: Optional[str] = None


class ScheduleDraft(BaseModel):
    title: str
    category: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    memo: Optional[str] = None
    priority: Priority = Priority.medium
    source: Source = Source.ai


class ScheduleParseData(BaseModel):
    intent: str = Field(..., description="e.g. create_schedule, create_todo, query, unknown")
    confidence: float
    slots: ScheduleSlots
    schedule_draft: ScheduleDraft
    missing_fields: List[str] = Field(default_factory=list)
    tts_text: Optional[str] = Field(
        None,
        description="음성 안내용 문장. 성공/부분인식/실패에 따라 달라지며 Flutter TTS로 재생한다.",
    )


class ScheduleParseResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ScheduleParseData] = None
