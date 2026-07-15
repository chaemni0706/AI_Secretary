"""Emotion analysis / life-coaching schemas (/api/v1/emotion).

Note: this is a life-coaching aid, NOT a medical diagnosis. Wording stays
suggestive ("보입니다", "추천합니다").
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RecentContext(BaseModel):
    sleep_hours: Optional[float] = None
    schedule_count: Optional[int] = None
    todo_done_rate: Optional[float] = Field(None, description="0~100 (%)")


class EmotionAnalyzeRequest(BaseModel):
    input: str = Field(..., description="감정 기록 문장")
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    recent_context: RecentContext = Field(default_factory=RecentContext)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input": "오늘 너무 피곤하고 아무것도 하기 싫어",
                "date": "2026-06-30",
                "recent_context": {
                    "sleep_hours": 4.5,
                    "schedule_count": 5,
                    "todo_done_rate": 30,
                },
            }
        }
    )


class EmotionAnalyzeData(BaseModel):
    sentiment: str = Field(..., description="positive | neutral | negative")
    emotion: str = Field(..., description="fatigue | anxiety | sadness | anger | stress | positive | neutral")
    emotion_score: float = Field(..., description="0.0 ~ 1.0")
    risk_level: str = Field(..., description="low | medium | high")
    coaching: str
    recommended_actions: List[str] = Field(default_factory=list)


class EmotionAnalyzeResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[EmotionAnalyzeData] = None
