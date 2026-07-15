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


class BriefingWeather(BaseModel):
    """오늘 날씨 요약(선택). 프론트가 /weather 결과에서 추려 함께 보낸다.

    값이 없으면(미전송/오프라인) 브리핑은 기존과 동일하게 날씨 없이 생성된다.
    """

    sky: Optional[str] = Field(None, description="맑음 | 구름많음 | 흐림")
    precipitation: Optional[str] = Field(None, description="없음 | 비 | 비/눈 | 눈 | 소나기")
    temp_c: Optional[float] = Field(None, description="현재 기온(℃)")
    temp_min: Optional[float] = Field(None, description="오늘 최저(℃)")
    temp_max: Optional[float] = Field(None, description="오늘 최고(℃)")
    max_pop: Optional[int] = Field(None, description="당일 최대 강수확률(%)")


class DailyBriefingRequest(BaseModel):
    date: str = Field(..., description="Target day 'YYYY-MM-DD'")
    schedules: List[BriefingSchedule] = Field(default_factory=list)
    todos: List[BriefingTodo] = Field(default_factory=list)
    weather: Optional[BriefingWeather] = Field(
        None, description="오늘 날씨 요약(선택). 있으면 브리핑에 날씨 안내/준비 팁을 추가한다."
    )

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
