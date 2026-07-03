"""travel_time_service tests (Maps client mocked at the function level)."""

import pytest

from backend.services import travel_time_service as svc
from backend.services import naver_maps_client as maps

_CAR = {
    "distance_meters": 3200, "duration_minutes": 18, "duration_ms": 1080000,
    "route_summary": "자동차 기준 약 18분 소요", "transport_mode": "car", "source": "naver_maps",
}


# 4. destination coords absent + address present -> geocode then directions
def test_estimate_geocodes_then_directions(monkeypatch):
    calls = {"geocode": 0, "directions": 0}

    def _geo(addr):
        calls["geocode"] += 1
        return {"latitude": 37.5541, "longitude": 126.9223,
                "road_address": "서울 마포구 양화로 ...", "jibun_address": None}

    def _dir(o_lat, o_lng, d_lat, d_lng, option="trafast"):
        calls["directions"] += 1
        assert (d_lat, d_lng) == (37.5541, 126.9223)
        return dict(_CAR)

    monkeypatch.setattr(svc.maps, "geocode", _geo)
    monkeypatch.setattr(svc.maps, "directions", _dir)

    out = svc.estimate_travel(
        origin={"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
        destination={"address": "서울 마포구 양화로 ...", "latitude": None, "longitude": None},
        transport_mode="car",
    )
    assert calls == {"geocode": 1, "directions": 1}
    assert out["travel"]["duration_minutes"] == 18
    assert out["destination"]["latitude"] == 37.5541


# 5. transport_mode car -> directions used, coords passed straight through
def test_car_uses_directions_without_geocode(monkeypatch):
    monkeypatch.setattr(svc.maps, "geocode", lambda a: pytest.fail("geocode should not run"))
    monkeypatch.setattr(svc.maps, "directions", lambda *a, **k: dict(_CAR))
    out = svc.estimate_travel(
        origin={"latitude": 37.5572, "longitude": 126.9245},
        destination={"latitude": 37.5541, "longitude": 126.9223},
        transport_mode="car",
    )
    assert out["travel"]["transport_mode"] == "car"
    assert out["travel"]["duration_minutes"] == 18


# 6. public_transit -> car reference + fallback note
def test_public_transit_fallback_note(monkeypatch):
    monkeypatch.setattr(svc.maps, "directions", lambda *a, **k: dict(_CAR))
    out = svc.compute_travel(37.5572, 126.9245, 37.5541, 126.9223, transport_mode="public_transit")
    assert out["transport_mode"] == "public_transit"
    assert "note" in out and "대중교통" in out["note"]


# walking -> straight-line estimate, no Maps call
def test_walking_uses_straight_line(monkeypatch):
    monkeypatch.setattr(svc.maps, "directions", lambda *a, **k: pytest.fail("no directions for walking"))
    out = svc.compute_travel(37.5572, 126.9245, 37.5541, 126.9223, transport_mode="walking")
    assert out["transport_mode"] == "walking"
    assert out["duration_minutes"] >= 1
    assert out["source"] == "estimate"


def test_missing_origin_coords_raises_value_error(monkeypatch):
    with pytest.raises(ValueError):
        svc.estimate_travel(
            origin={"address": "홍대입구역"},
            destination={"latitude": 37.55, "longitude": 126.92},
        )


def test_safe_compute_never_raises(monkeypatch):
    def _boom(*a, **k):
        raise maps.NaverMapsApiError("down")
    monkeypatch.setattr(svc.maps, "directions", _boom)
    assert svc.safe_compute_travel(37.5, 126.9, 37.6, 127.0, "car") is None
    assert svc.safe_compute_travel(None, None, 37.6, 127.0, "car") is None
