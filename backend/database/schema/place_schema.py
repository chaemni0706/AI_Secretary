"""Place recommendation schemas (/api/v1/places).

MVP: search + score + return. Most request fields are optional so a bare
`input` (or bare `preferences.category`) is enough to get recommendations.

Travel-time integration is additive: set options.include_travel_time and
provide location coords to get per-place travel info + travel-aware scoring.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.travel_schema import TravelInfo


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


class PlaceOptions(BaseModel):
    """Optional, additive behavior toggles."""

    include_travel_time: bool = Field(
        True,
        description=(
            "기본 True. 사용자 위치 좌표가 있으면 상위 N개 장소에 이동 시간을 계산해 "
            "포함하고, 일정(가능 시간대)이 주어지면 이동+체류 시간으로 실현 가능성까지 "
            "점수에 반영. 명시적으로 False를 주면 이동 시간 계산을 끕니다."
        ),
    )
    transport_mode: str = Field("car", description="car | public_transit | walking | unknown")


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
    options: Optional[PlaceOptions] = None

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
                "options": {"include_travel_time": True},
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
    travel: Optional[TravelInfo] = Field(
        None, description="자동차 기준 이동 정보. 상위 N개에만 채워짐"
    )
    travel_walk: Optional[TravelInfo] = Field(
        None,
        description=(
            "도보 이동 정보. 도보 예상 시간이 walk_show_max_minutes(기본 15분) 이하일 "
            "때만 채워지고, 그보다 멀면 null."
        ),
    )
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
