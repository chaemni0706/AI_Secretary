"""Personalization schemas — connect stored user preferences to reservation
candidate ranking, notification reminders and emotion coaching.

Backed by the EXISTING user_memories table (no schema change): richer
preference fields are stored as PREFERENCE rows under `pref_*` keys, layered on
top of the legacy memory_service values. All models are additive; existing
memory / reservation / emotion contracts are untouched.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Allowed value sets (invalid values fall back to defaults in preference_service)
TIME_BUCKETS = ("early_morning", "morning", "afternoon", "evening", "late_night")
TONES = ("neutral", "gentle", "warm")
COACHING_STYLES = ("supportive", "direct", "coaching")
NOTIFICATION_STYLES = ("normal", "soft", "strong")


class Personalization(BaseModel):
    """Metadata every personalized response carries so Flutter can show whether
    (and how) the user's stored preferences shaped the result."""

    personalization_applied: bool = False
    memory_source: str = "default_preference"   # stored_preference | default_preference
    used_preferences: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class UserPreference(BaseModel):
    """Effective, merged preference (stored over defaults)."""

    user_id: str = "local-user"
    preferred_reservation_times: List[str] = Field(default_factory=lambda: ["afternoon", "evening"])
    avoid_times: List[str] = Field(default_factory=list)
    default_reminder_minutes: int = 30
    departure_buffer_minutes: int = 10
    late_prone: bool = False
    preferred_tone: str = "neutral"
    coaching_style: str = "supportive"
    stress_triggers: List[str] = Field(default_factory=list)
    rest_recommendation_enabled: bool = True
    notification_style: str = "normal"


class PreferenceUpdate(BaseModel):
    """PUT body — only provided fields are written. Invalid values are ignored."""

    preferred_reservation_times: Optional[List[str]] = None
    avoid_times: Optional[List[str]] = None
    default_reminder_minutes: Optional[int] = None
    departure_buffer_minutes: Optional[int] = None
    late_prone: Optional[bool] = None
    preferred_tone: Optional[str] = None
    coaching_style: Optional[str] = None
    stress_triggers: Optional[List[str]] = None
    rest_recommendation_enabled: Optional[bool] = None
    notification_style: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "preferred_reservation_times": ["evening"],
                "avoid_times": ["early_morning"],
                "default_reminder_minutes": 40,
                "departure_buffer_minutes": 15,
                "late_prone": True,
                "preferred_tone": "gentle",
                "coaching_style": "supportive",
                "stress_triggers": ["과제", "마감"],
                "rest_recommendation_enabled": True,
                "notification_style": "soft",
            }
        }
    )


class PreferenceResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Notification reminder recommendation
# --------------------------------------------------------------------------- #
class ReminderRecommendRequest(BaseModel):
    user_id: str = "local-user"
    title: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: Optional[str] = Field(None, description="'HH:MM'")
    travel_minutes: Optional[int] = Field(None, description="이동 소요(분). 없으면 출발 알림 생략")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user", "title": "병원 예약", "category": "health",
                "date": "2026-07-01", "start_time": "15:00", "travel_minutes": 30,
            }
        }
    )


class ReminderItem(BaseModel):
    type: str                      # default | departure
    minutes_before: int
    message: str


class ReminderRecommendData(BaseModel):
    reminders: List[ReminderItem] = Field(default_factory=list)
    personalization: Personalization = Field(default_factory=Personalization)


class ReminderRecommendResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ReminderRecommendData] = None


# --------------------------------------------------------------------------- #
# Emotion coaching (preference-aware, non-diagnostic)
# --------------------------------------------------------------------------- #
class EmotionCoachRequest(BaseModel):
    user_id: str = "local-user"
    text: str = Field(..., min_length=1, description="감정 기록 문장")
    sleep_hours: Optional[float] = None
    schedule_count: Optional[int] = None
    todo_done_rate: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"user_id": "local-user", "text": "과제 마감 때문에 너무 스트레스 받아"}
        }
    )


class EmotionCoachData(BaseModel):
    emotion: str
    coaching_message: str
    suggested_actions: List[str] = Field(default_factory=list)
    personalization: Personalization = Field(default_factory=Personalization)


class EmotionCoachResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[EmotionCoachData] = None
