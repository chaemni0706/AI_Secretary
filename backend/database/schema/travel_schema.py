"""Travel time / distance schemas (/api/v1/travel).

Also exports TravelInfo, reused (optionally) by place recommendation and
departure-alert responses.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GeoPoint(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class TravelDestination(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    road_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TravelInfo(BaseModel):
    """Shared travel result block."""

    distance_meters: Optional[int] = None
    duration_minutes: Optional[int] = None
    transport_mode: str = "car"
    route_summary: Optional[str] = None
    source: str = "naver_maps"
    note: Optional[str] = None


class TravelEstimateRequest(BaseModel):
    user_id: Optional[str] = None
    current_datetime: Optional[str] = Field(None, description="ISO 8601")
    timezone: Optional[str] = "Asia/Seoul"
    origin: GeoPoint
    destination: TravelDestination
    transport_mode: str = Field("car", description="car | public_transit | walking | unknown")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user-1",
                "current_datetime": "2026-07-03T17:30:00+09:00",
                "timezone": "Asia/Seoul",
                "origin": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
                "destination": {
                    "name": "홍대 한식당 예시",
                    "address": "서울 마포구 양화로 ...",
                    "road_address": "서울 마포구 양화로 ...",
                    "latitude": None,
                    "longitude": None,
                },
                "transport_mode": "car",
            }
        }
    )


class TravelResolvedOrigin(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class TravelResolvedDestination(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class TravelEstimateData(BaseModel):
    origin: TravelResolvedOrigin
    destination: TravelResolvedDestination
    travel: TravelInfo


class TravelEstimateResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[TravelEstimateData] = None
