"""Voice endpoints — TTS fallback.

MVP 정책: 서버에서 음성 파일을 합성하지 않는다. 클라이언트(Flutter)의
`flutter_tts` 로 재생할 "문장"만 표준 envelope 로 돌려주는 fallback 이다.
추후 서버 TTS(오디오 파일 생성)를 붙일 때 `mode`/`audio_url` 필드를 채우는
방식으로 확장할 수 있도록 응답 형태를 미리 고정해 둔다.

Endpoint:
  * POST /api/v1/voice/tts  — 재생할 문장을 flutter_tts fallback 형태로 반환.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend.core.response import success_response

router = APIRouter(tags=["voice"])


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, description="음성으로 재생할 문장")
    source: str = Field(
        "chatbot_reply",
        description="호출 맥락 구분용(예: voice_schedule, briefing, call_alert)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"text": "일정이 등록됐어요.", "source": "voice_schedule"}
        }
    )


class TtsData(BaseModel):
    mode: str = "flutter_tts"
    text: str
    audio_url: Optional[str] = None
    mime_type: Optional[str] = None
    duration_seconds: Optional[float] = None
    voice_id: str = "device_default"
    cached: bool = False


class TtsResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[TtsData] = None


@router.post(
    "/voice/tts",
    response_model=TtsResponse,
    summary="TTS fallback (flutter_tts 재생 문장 반환)",
)
async def voice_tts_endpoint(req: TtsRequest):
    data = TtsData(text=req.text.strip())
    return success_response(
        message="Flutter TTS로 재생할 문장을 반환했습니다.",
        data=data.model_dump(),
    )
