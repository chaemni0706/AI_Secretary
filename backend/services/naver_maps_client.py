"""Naver Cloud Maps API client.

Single responsibility: call Naver Cloud Maps endpoints (Geocoding,
Reverse Geocoding, Directions 5) and return *internal-format* dicts. No
scoring/planning here.

Auth is SEPARATE from the local-search API — these use the Naver Cloud API
Gateway credentials (`NAVER_MAPS_CLIENT_ID` / `NAVER_MAPS_CLIENT_SECRET`).

Errors are typed so callers can degrade gracefully instead of 500ing:
    NaverMapsConfigError  -> credentials missing/invalid
    NaverMapsApiError     -> network / HTTP / parse failure
"""

from __future__ import annotations

import math
from typing import List, Optional

import httpx

from backend.core.config import settings


class NaverMapsError(Exception):
    """Base class for Naver Maps client errors."""


class NaverMapsConfigError(NaverMapsError):
    """Raised when Naver Cloud Maps credentials are missing or empty."""


class NaverMapsApiError(NaverMapsError):
    """Raised when a Maps API call fails (network/HTTP/parse)."""


def _headers() -> dict:
    if not settings.naver_maps_configured:
        raise NaverMapsConfigError(
            "네이버 클라우드 Maps API 키가 설정되지 않았습니다. "
            "backend/.env에 NAVER_MAPS_CLIENT_ID와 NAVER_MAPS_CLIENT_SECRET를 설정하세요."
        )
    return {
        "x-ncp-apigw-api-key-id": settings.NAVER_MAPS_CLIENT_ID,
        "x-ncp-apigw-api-key": settings.NAVER_MAPS_CLIENT_SECRET,
        "Accept": "application/json",
    }


def _get(url: str, params: dict) -> dict:
    """GET with shared error handling; returns parsed JSON dict."""
    headers = _headers()  # may raise NaverMapsConfigError
    try:
        resp = httpx.get(
            url, headers=headers, params=params,
            timeout=settings.NAVER_MAPS_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise NaverMapsApiError(f"네이버 Maps API 호출에 실패했습니다: {exc}") from exc

    if resp.status_code in (401, 403):
        raise NaverMapsConfigError("네이버 Maps API 인증에 실패했습니다. 키를 확인하세요.")
    if resp.status_code != 200:
        raise NaverMapsApiError(
            f"네이버 Maps API가 오류를 반환했습니다 (status={resp.status_code})."
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise NaverMapsApiError("네이버 Maps API 응답을 해석할 수 없습니다.") from exc


# --------------------------------------------------------------------------- #
# Geocoding: 주소 -> 좌표
# --------------------------------------------------------------------------- #
def geocode(address: str) -> Optional[dict]:
    """Convert an address to coordinates. Returns None when no match.

    Internal format::
        {"latitude": float, "longitude": float,
         "road_address": str|None, "jibun_address": str|None}
    """
    address = (address or "").strip()
    if not address:
        return None
    payload = _get(settings.NAVER_MAPS_GEOCODE_URL, {"query": address})
    addresses = payload.get("addresses") or []
    if not addresses:
        return None
    top = addresses[0]
    try:
        lng = float(top.get("x"))
        lat = float(top.get("y"))
    except (TypeError, ValueError) as exc:
        raise NaverMapsApiError("Geocoding 좌표를 해석할 수 없습니다.") from exc
    return {
        "latitude": lat,
        "longitude": lng,
        "road_address": (top.get("roadAddress") or "").strip() or None,
        "jibun_address": (top.get("jibunAddress") or "").strip() or None,
    }


# --------------------------------------------------------------------------- #
# Reverse Geocoding: 좌표 -> 주소  (MVP 선택 구현)
# --------------------------------------------------------------------------- #
def reverse_geocode(latitude: float, longitude: float) -> Optional[dict]:
    """Convert coordinates to an address string. Best-effort; may return None."""
    params = {
        "coords": f"{longitude},{latitude}",
        "output": "json",
        "orders": "roadaddr,addr",
    }
    payload = _get(settings.NAVER_MAPS_REVERSE_GEOCODE_URL, params)
    results = payload.get("results") or []
    if not results:
        return None
    r = results[0]
    region = r.get("region", {}) or {}
    parts = [
        (region.get("area1", {}) or {}).get("name", ""),
        (region.get("area2", {}) or {}).get("name", ""),
        (region.get("area3", {}) or {}).get("name", ""),
    ]
    land = r.get("land", {}) or {}
    road = " ".join(p for p in parts if p)
    if land.get("name"):
        road = f"{road} {land.get('name')}".strip()
    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": road or None,
    }


# --------------------------------------------------------------------------- #
# Directions 5: 출발지 -> 목적지 거리/시간 (자동차 기준)
# --------------------------------------------------------------------------- #
def _ms_to_minutes(duration_ms: Optional[float]) -> Optional[int]:
    """Directions duration arrives in milliseconds -> ceil to minutes."""
    if duration_ms is None:
        return None
    try:
        return math.ceil(float(duration_ms) / 1000 / 60)
    except (TypeError, ValueError):
        return None


def directions(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    option: str = "trafast",
) -> dict:
    """Driving route between two coordinates.

    Internal format::
        {"distance_meters": int, "duration_minutes": int, "duration_ms": int,
         "route_summary": str, "transport_mode": "car", "source": "naver_maps"}
    """
    params = {
        "start": f"{origin_lng},{origin_lat}",
        "goal": f"{dest_lng},{dest_lat}",
        "option": option,
    }
    payload = _get(settings.NAVER_MAPS_DIRECTIONS_URL, params)

    # Directions 5 shape: route -> {<option>: [ {summary: {distance, duration}} ]}
    route = payload.get("route") or {}
    legs: List[dict] = []
    for key in (option, "trafast", "traoptimal", "tracomfort"):
        if route.get(key):
            legs = route[key]
            break
    if not legs:
        raise NaverMapsApiError("경로를 찾을 수 없습니다.")

    summary = (legs[0] or {}).get("summary", {}) or {}
    distance_m = summary.get("distance")
    duration_ms = summary.get("duration")
    minutes = _ms_to_minutes(duration_ms)
    if minutes is None or distance_m is None:
        raise NaverMapsApiError("경로 거리/시간을 해석할 수 없습니다.")

    return {
        "distance_meters": int(distance_m),
        "duration_minutes": minutes,
        "duration_ms": int(duration_ms),
        "route_summary": f"자동차 기준 약 {minutes}분 소요",
        "transport_mode": "car",
        "source": "naver_maps",
    }
