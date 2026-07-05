"""User AI-voice-response style preferences (assistant_tone / response_length /
nudge_strength). Rule-based MVP: settings are chosen in the Flutter settings
screen (NOT parsed from voice), stored via user_preference_service, and
consumed by tts_response_builder wherever a tts_text is generated.

Kept in the project's common {success, message, data} envelope so the
existing Flutter `ApiClient.getData/postData` helpers work unchanged.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.response import success_response
from backend.services import tts_response_builder, user_preference_service

router = APIRouter(tags=["user_preferences"])


class UserPreferencesPatch(BaseModel):
    user_id: Optional[str] = Field("local-user", description="없으면 'local-user'")
    assistant_tone: Optional[str] = Field(None, description="polite | friendly | concise | caring | professional")
    response_length: Optional[str] = Field(None, description="short | normal | detailed")
    nudge_strength: Optional[str] = Field(None, description="low | medium | high")


def _confirmation_sentence(prefs: dict) -> str:
    """A short TTS-ready confirmation sentence for the settings screen itself.
    Not one of the 16 voice-flow intents, so it's assembled directly from
    tone_profiles display names rather than routed through
    tts_response_builder's response_templates.json."""
    tones = tts_response_builder.load_tone_profiles()
    tone_name = tones.get(prefs["assistant_tone"], {}).get("display_name", prefs["assistant_tone"])
    length_name = {"short": "짧게", "normal": "보통 길이로", "detailed": "자세하게"}.get(
        prefs["response_length"], prefs["response_length"]
    )
    nudge_name = {"low": "거의 하지 않도록", "medium": "적당히", "high": "꼼꼼하게"}.get(
        prefs["nudge_strength"], prefs["nudge_strength"]
    )
    return f"설정을 저장했습니다. 앞으로 {tone_name} 말투로 {length_name} 답변드리고, 리마인드는 {nudge_name} 챙겨드릴게요."


@router.get(
    "/user/preferences",
    summary="AI 음성 응답 스타일 설정 조회 (없으면 기본값)",
)
def get_user_preferences(user_id: str = "local-user"):
    preferences = user_preference_service.get_user_preferences(user_id)
    return success_response(
        message="사용자 선호 설정을 불러왔습니다.",
        data={
            "user_id": user_id,
            "preferences": preferences,
            "options": user_preference_service.get_options(),
        },
    )


@router.put(
    "/user/preferences",
    summary="AI 음성 응답 스타일 설정 저장 (일부 값만 보내도 나머지는 유지)",
)
def put_user_preferences(payload: UserPreferencesPatch):
    user_id = payload.user_id or "local-user"
    updates = payload.model_dump(exclude={"user_id"}, exclude_none=True)
    preferences = user_preference_service.update_user_preferences(user_id, updates)
    return success_response(
        message="설정을 저장했습니다.",
        data={
            "user_id": user_id,
            "preferences": preferences,
            "tts_text": _confirmation_sentence(preferences),
        },
    )
