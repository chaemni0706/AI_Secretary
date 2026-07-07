"""Weather endpoint — 기상청 단기예보(현재+오늘). 키 없으면 Mock."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from backend.core.response import success_response
from backend.database.schema.weather_schema import WeatherResponse
from backend.services import weather_service

router = APIRouter(tags=["weather"])


@router.get("/weather", response_model=WeatherResponse, summary="현재+오늘 날씨(기상청)")
def get_weather_endpoint(
    lat: Optional[float] = Query(None, description="위도(없으면 서울 기본 격자)"),
    lon: Optional[float] = Query(None, description="경도"),
):
    data = weather_service.get_weather(lat=lat, lon=lon)
    return success_response(message="날씨 정보입니다.", data=data.model_dump())
