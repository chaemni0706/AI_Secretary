"""Voice input routing schemas (/api/v1/voice/route).

Additive, brand-new module: a single voice utterance is classified into one of
7 intents (see ``voice_intent_router.py``) and dispatched to the EXISTING
service for that intent (place recommendation / chat orchestrator / briefing
generator / schedule parser / notification plan builder). No existing schema
is touched by this file.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScreenAction(BaseModel):
    type: str = Field("none", description="navigate | show_card | show_bottom_sheet | none")
    target: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class VoiceRouteRequest(BaseModel):
    text: str = Field(..., min_length=1, description="STT로 인식된 사용자 발화")
    user_id: Optional[str] = "local-user"
    current_datetime: Optional[str] = Field(None, description="ISO 8601 (caller's 'now')")
    timezone: str = "Asia/Seoul"
    location: Optional[Dict[str, Any]] = Field(
        None, description="{latitude, longitude, address} — 장소 추천에 한해 사용, 선택"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "직전 turn에서 서버가 돌려준 data.context 를 그대로 echo. "
            "reminder_setting 은 이 값이 {'type': 'schedule_created', ...} 일 때만 동작한다."
        ),
    )
    # --- optional AI voice-style passthrough (mirrors ScheduleParseRequest) ---
    assistant_tone: Optional[str] = None
    response_length: Optional[str] = None
    reminder_strength: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "가게 추천해줘",
                "current_datetime": "2026-07-06T09:00:00+09:00",
                "context": None,
            }
        }
    )


class VoiceRouteData(BaseModel):
    intent: str = Field(
        ...,
        description=(
            "reservation_recommendation | emotion_schedule_coaching | daily_briefing | "
            "schedule_query | reminder_setting | schedule_create | fallback_chat"
        ),
    )
    tts_text: str
    screen_action: ScreenAction
    data: Dict[str, Any] = Field(default_factory=dict, description="intent별 상세 payload (자유 형식, additive)")
    context: Optional[Dict[str, Any]] = Field(
        None, description="다음 turn 요청에 그대로 되돌려 보내야 하는 pending context (없으면 null)"
    )
    debug: Optional[Dict[str, Any]] = Field(
        None, description="분류 근거(matched keywords 등). 디버깅 전용 — 프론트는 무시해도 된다."
    )


class VoiceRouteResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[VoiceRouteData] = None
