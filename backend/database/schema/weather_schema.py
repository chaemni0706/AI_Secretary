"""Weather (기상청 단기예보) response schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class WeatherNow(BaseModel):
    temp_c: Optional[float] = Field(None, description="현재 기온(℃)")
    sky: Optional[str] = Field(None, description="하늘: 맑음|구름많음|흐림")
    precipitation: Optional[str] = Field(None, description="강수형태: 없음|비|비/눈|눈|소나기")
    humidity: Optional[int] = Field(None, description="습도(%)")
    summary: Optional[str] = Field(None, description="한 줄 요약(예: '맑음, 24℃')")


class WeatherHour(BaseModel):
    time: str = Field(..., description="'HH:mm'")
    temp_c: Optional[float] = None
    sky: Optional[str] = None
    precipitation: Optional[str] = None
    pop: Optional[int] = Field(None, description="강수확률(%)")


class WeatherData(BaseModel):
    location: str = Field("현재 위치", description="표시용 위치명")
    nx: int
    ny: int
    now: WeatherNow
    today: List[WeatherHour] = Field(default_factory=list, description="오늘 시간별 예보")
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    source: str = Field("kma", description="kma | mock")
    observed_at: Optional[str] = Field(None, description="기준 발표 시각")


class WeatherResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[WeatherData] = None
