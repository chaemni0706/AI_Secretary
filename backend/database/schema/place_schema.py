"""Place recommendation schemas (/api/v1/places).

MVP: search + score + return. Most request fields are optional so a bare
`input` (or bare `preferences.category`) is enough to get recommendations.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #
class PlaceLocation(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = Field(None, description="사람이 읽는 위치 텍스트 (검색어 보강에 사용)")


class PlacePreferences(BaseModel):
    category: Optional[str] = Field(
        None, description="restaurant | cafe | activity | beauty | hospital"
    )
    keywords: List[str] = Field(default_factory=list)
    max_distance_meters: Optional[int] = None
    price_level: Optional[str] = Field(None, description="low | medium | high")
    mood: Optional[str] = Field(None, description="casual | date | quiet ...")


class PlaceScheduleContext(BaseModel):
    available_start_time: Optional[str] = Field(None, description="'HH:mm'")
    available_end_time: Optional[str] = Field(None, description="'HH:mm'")
    duration_minutes: Optional[int] = None


class PlaceRecommendRequest(BaseModel):
    """Everything optional except that we need *something* to search with:
    either `input` text or `preferences.category`. Validated in the service,
    not here, so MVP callers never hit hard 422s for partial payloads."""

    user_id: Optional[str] = None
    input: Optional[str] = Field(None, description="사용자 자연어 입력")
    current_datetime: Optional[str] = Field(None, description="ISO 8601")
    timezone: Optional[str] = "Asia/Seoul"
    location: Optional[PlaceLocation] = None
    preferences: Optional[PlacePreferences] = None
    schedule_context: Optional[PlaceScheduleContext] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user-1",
                "input": "홍대 근처에서 저녁 먹을 만한 식당 추천해줘",
                "current_datetime": "2026-07-03T18:00:00+09:00",
                "timezone": "Asia/Seoul",
                "location": {
                    "latitude": 37.5572,
                    "longitude": 126.9245,
                    "address": "홍대입구역",
                },
                "preferences": {
                    "category": "restaurant",
                    "keywords": ["저녁", "한식", "가성비"],
                    "max_distance_meters": 1500,
                    "price_level": "medium",
                    "mood": "casual",
                },
                "schedule_context": {
                    "available_start_time": "18:30",
                    "available_end_time": "21:00",
                    "duration_minutes": 90,
                },
            }
        }
    )


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #
class RecommendedPlace(BaseModel):
    place_id: str
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    map_url: Optional[str] = None
    score: int = Field(..., description="0 ~ 100, higher is better")
    reason: str
    recommendation_tags: List[str] = Field(default_factory=list)
    source: str = "naver"


class PlaceRecommendFilters(BaseModel):
    category: Optional[str] = None
    max_distance_meters: Optional[int] = None
    available_time: Optional[str] = None


class PlaceRecommendData(BaseModel):
    query: str
    recommended_places: List[RecommendedPlace] = Field(default_factory=list)
    filters: PlaceRecommendFilters


class PlaceRecommendResponse(BaseModel):
    """Documents the response shape in Swagger; runtime uses the shared
    {success, message, data} envelope from core.response."""

    success: bool = True
    message: str = "OK"
    data: Optional[PlaceRecommendData] = None
