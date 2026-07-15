"""Preparation / departure alert schemas (/api/v1/alerts).

Legacy contract (schedule/context/user_preference -> leave_time/checklist/
notifications) is UNCHANGED. Travel-aware fields (schedule coords, user_profile,
options) are all optional and additive; when options.include_travel_time is set,
the endpoint returns the richer `alert_plan` shape instead.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.travel_schema import TravelInfo


class AlertSchedule(BaseModel):
    title: str
    category: str = Field("etc", description="hospital | school | meeting | beauty | exercise | travel | etc")
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    location: Optional[str] = None
    # --- optional, additive (travel-aware) ---
    id: Optional[str] = None
    end_time: Optional[str] = Field(None, description="'HH:mm'")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    priority: Optional[str] = None
    is_fixed: Optional[bool] = None


class AlertContext(BaseModel):
    weather: Optional[str] = Field(None, description="rain | snow | hot | cold | clear ...")
    estimated_travel_minutes: int = 0
    buffer_minutes: int = 0


class UserPreference(BaseModel):
    notification_style: str = Field("normal", description="normal | strong")
    forgetful: bool = False
    late_prone: bool = Field(
        False, description="지각 성향: True면 출발 시각 N분 전 추가 알림(선택, 기본 False)"
    )


class AlertCurrentLocation(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class UserProfile(BaseModel):
    """Optional travel-aware profile (used only on the travel path)."""

    default_alert_minutes_before: int = 30
    departure_buffer_minutes: int = 10
    transport_mode: str = "car"
    late_prone: bool = False
    current_location: Optional[AlertCurrentLocation] = None


class AlertOptions(BaseModel):
    include_checklist: bool = True
    include_departure_alert: bool = True
    include_mock_call_alert: bool = False
    include_travel_time: bool = False
    voice_enabled: bool = False


class ChecklistItem(BaseModel):
    item: str
    reason: str


class NotificationItem(BaseModel):
    time: str = Field(..., description="'HH:mm'")
    message: str


class DeparturePlanRequest(BaseModel):
    schedule: AlertSchedule
    context: AlertContext = Field(default_factory=AlertContext)
    user_preference: UserPreference = Field(default_factory=UserPreference)
    # --- optional, additive (travel-aware) ---
    user_id: Optional[str] = None
    current_datetime: Optional[str] = Field(None, description="ISO 8601")
    timezone: Optional[str] = "Asia/Seoul"
    user_profile: Optional[UserProfile] = None
    options: Optional[AlertOptions] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule": {
                    "title": "병원 예약",
                    "category": "hospital",
                    "date": "2026-06-30",
                    "start_time": "14:00",
                    "location": "서울OO병원",
                },
                "context": {
                    "weather": "rain",
                    "estimated_travel_minutes": 35,
                    "buffer_minutes": 10,
                },
                "user_preference": {"notification_style": "strong", "forgetful": True, "late_prone": True},
            }
        }
    )


class DeparturePlanData(BaseModel):
    leave_time: Optional[str] = Field(None, description="'HH:mm'")
    estimated_travel_minutes: int
    buffer_minutes: int
    checklist: List[ChecklistItem] = Field(default_factory=list)
    notifications: List[NotificationItem] = Field(default_factory=list)


class DeparturePlanResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[DeparturePlanData] = None


# --------------------------------------------------------------------------- #
# Travel-aware alert plan (returned only when options.include_travel_time=true)
# --------------------------------------------------------------------------- #
class TravelAwareReminder(BaseModel):
    reminder_id: str
    type: str = "departure"
    trigger_datetime: Optional[str] = None
    departure_time: Optional[str] = Field(None, description="'HH:mm'")
    title: str
    message: str
    notification_channel: str = "local_push"


class AlertPlan(BaseModel):
    travel: Optional[TravelInfo] = None
    reminders: List[TravelAwareReminder] = Field(default_factory=list)
    voice_alert_text: Optional[str] = None
    save_required_on_frontend: bool = True


class DepartureAlertPlanData(BaseModel):
    schedule_id: Optional[str] = None
    alert_plan: AlertPlan
