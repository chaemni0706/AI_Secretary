"""Naver Cloud Maps client tests (no real API calls; httpx mocked)."""

import httpx
import pytest

from backend.core.config import settings
from backend.services import naver_maps_client as maps
from backend.services.naver_maps_client import NaverMapsApiError, NaverMapsConfigError


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def maps_keys(monkeypatch):
    monkeypatch.setattr(settings, "NAVER_MAPS_CLIENT_ID", "map-id")
    monkeypatch.setattr(settings, "NAVER_MAPS_CLIENT_SECRET", "map-secret")


# 1. Missing credentials -> clear config error
def test_missing_maps_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "NAVER_MAPS_CLIENT_ID", None)
    monkeypatch.setattr(settings, "NAVER_MAPS_CLIENT_SECRET", None)
    with pytest.raises(NaverMapsConfigError):
        maps.geocode("서울 마포구 양화로 100")


# 2. Geocoding response -> internal coordinate format
def test_geocode_normalizes(monkeypatch, maps_keys):
    payload = {"addresses": [{
        "x": "126.9245", "y": "37.5572",
        "roadAddress": "서울 마포구 양화로 100",
        "jibunAddress": "서울 마포구 서교동 1-1",
    }]}
    monkeypatch.setattr(maps.httpx, "get", lambda *a, **k: _FakeResp(200, payload))
    out = maps.geocode("서울 마포구 양화로 100")
    assert out["latitude"] == 37.5572
    assert out["longitude"] == 126.9245
    assert out["road_address"] == "서울 마포구 양화로 100"


def test_geocode_empty_returns_none(monkeypatch, maps_keys):
    monkeypatch.setattr(maps.httpx, "get", lambda *a, **k: _FakeResp(200, {"addresses": []}))
    assert maps.geocode("존재하지 않는 주소") is None


# 3. Directions duration (milliseconds) -> minutes
def test_directions_ms_to_minutes(monkeypatch, maps_keys):
    payload = {"route": {"trafast": [{"summary": {"distance": 3200, "duration": 1080000}}]}}
    monkeypatch.setattr(maps.httpx, "get", lambda *a, **k: _FakeResp(200, payload))
    out = maps.directions(37.5572, 126.9245, 37.5541, 126.9223)
    assert out["distance_meters"] == 3200
    assert out["duration_minutes"] == 18          # ceil(1080000/1000/60)
    assert out["transport_mode"] == "car"
    assert out["source"] == "naver_maps"


def test_directions_http_error_raises(monkeypatch, maps_keys):
    monkeypatch.setattr(maps.httpx, "get", lambda *a, **k: _FakeResp(500, {}))
    with pytest.raises(NaverMapsApiError):
        maps.directions(37.5, 126.9, 37.6, 127.0)


def test_directions_network_error_raises(monkeypatch, maps_keys):
    def _boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(maps.httpx, "get", _boom)
    with pytest.raises(NaverMapsApiError):
        maps.directions(37.5, 126.9, 37.6, 127.0)
