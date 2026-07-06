"""Travel-time service.

Resolves destination coordinates (via Geocoding when only an address is given),
then computes distance + duration with the Directions 5 API (car). Handles
transport_mode fallbacks for MVP.

Public API:
    compute_travel(origin_lat, origin_lng, dest_lat, dest_lng, transport_mode)
        -> TravelInfo-shaped dict            (raises NaverMapsError on failure)
    safe_compute_travel(...) -> dict | None  (never raises; None on failure)
    estimate_travel(origin, destination, transport_mode) -> dict
        -> {"origin", "destination", "travel"}  (raises ValueError / NaverMapsError)
"""

from __future__ import annotations

import math
from typing import Optional

from backend.services import naver_maps_client as maps
from backend.services.naver_maps_client import NaverMapsError

# straight-line walking estimate: ~4.5 km/h => 75 m/min
_WALK_METERS_PER_MIN = 75.0


def _haversine_meters(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _walking_estimate(o_lat, o_lng, d_lat, d_lng) -> dict:
    dist = _haversine_meters(o_lat, o_lng, d_lat, d_lng)
    minutes = max(1, math.ceil(dist / _WALK_METERS_PER_MIN))
    return {
        "distance_meters": int(round(dist)),
        "duration_minutes": minutes,
        "transport_mode": "walking",
        "route_summary": f"도보 직선거리 기준 약 {minutes}분 (실제 경로는 별도 연동 필요)",
        "source": "estimate",
        "note": "도보는 직선거리 기반 추정치입니다. 실제 도보 경로 연동은 미구현입니다.",
    }


def compute_travel(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    transport_mode: str = "car",
) -> dict:
    """Compute travel between two coordinate pairs. Raises NaverMapsError on
    Directions failure (car / public_transit / unknown)."""
    mode = (transport_mode or "car").lower()

    if mode == "walking":
        return _walking_estimate(origin_lat, origin_lng, dest_lat, dest_lng)

    # car / public_transit / unknown -> Directions 5 (driving)
    result = maps.directions(origin_lat, origin_lng, dest_lat, dest_lng)

    if mode == "public_transit":
        minutes = result["duration_minutes"]
        result = {
            **result,
            "transport_mode": "public_transit",
            "route_summary": (
                f"자동차 기준 약 {minutes}분 (대중교통 기준 실제 시간은 별도 연동 필요)"
            ),
            "note": "대중교통 기준 실제 시간은 별도 연동 필요",
        }
    elif mode == "unknown":
        result = {**result, "transport_mode": "car"}
    return result


def safe_compute_travel(
    origin_lat: Optional[float],
    origin_lng: Optional[float],
    dest_lat: Optional[float],
    dest_lng: Optional[float],
    transport_mode: str = "car",
) -> Optional[dict]:
    """Best-effort travel: returns None instead of raising, so callers (place
    recommendation, departure alert) never fail because of Maps issues."""
    if None in (origin_lat, origin_lng, dest_lat, dest_lng):
        return None
    try:
        return compute_travel(origin_lat, origin_lng, dest_lat, dest_lng, transport_mode)
    except (NaverMapsError, Exception):
        return None


def _resolve_destination_coords(destination: dict) -> tuple:
    """Return (lat, lng) for the destination, geocoding an address if needed."""
    lat, lng = destination.get("latitude"), destination.get("longitude")
    if lat is not None and lng is not None:
        return lat, lng, None
    address = destination.get("road_address") or destination.get("address")
    if not address:
        raise ValueError("목적지 좌표 또는 주소가 필요합니다.")
    geo = maps.geocode(address)  # may raise NaverMapsError
    if not geo:
        raise ValueError("목적지 주소의 좌표를 찾을 수 없습니다.")
    return geo["latitude"], geo["longitude"], geo


def estimate_travel(
    origin: dict,
    destination: dict,
    transport_mode: str = "car",
) -> dict:
    """Full estimate used by POST /travel/estimate."""
    o_lat, o_lng = origin.get("latitude"), origin.get("longitude")
    if o_lat is None or o_lng is None:
        raise ValueError("출발지 좌표(origin.latitude/longitude)가 필요합니다.")

    d_lat, d_lng, geo = _resolve_destination_coords(destination)
    travel = compute_travel(o_lat, o_lng, d_lat, d_lng, transport_mode)

    dest_address = (
        destination.get("road_address")
        or destination.get("address")
        or (geo.get("road_address") if geo else None)
    )
    return {
        "origin": {
            "latitude": o_lat,
            "longitude": o_lng,
            "address": origin.get("address"),
        },
        "destination": {
            "name": destination.get("name"),
            "latitude": d_lat,
            "longitude": d_lng,
            "address": dest_address,
        },
        "travel": travel,
    }
