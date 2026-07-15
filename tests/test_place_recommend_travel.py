"""Place recommendation + travel integration tests (all external calls mocked).

POST /api/v1/places/recommend  with options.include_travel_time
"""

import pytest

from backend.core.config import settings
from backend.services import naver_place_client as naver
from backend.services import place_recommendation_service as place_svc

RECOMMEND = "/api/v1/places/recommend"


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _naver_payload():
    return {"items": [
        {"title": "<b>홍대</b> 한식당 예시", "link": "https://map.naver.com/x",
         "category": "한식>백반,가정식", "telephone": "02-000-0000",
         "address": "서울 마포구 서교동 1-1", "roadAddress": "서울 마포구 양화로 100"},
        {"title": "무관한 옷가게", "link": "", "category": "생활,편의>의류",
         "telephone": "", "address": "서울 마포구 서교동 2-2", "roadAddress": ""},
    ]}


@pytest.fixture
def search_ok(monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "s-id")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "s-secret")
    monkeypatch.setattr(naver.httpx, "get", lambda *a, **k: _FakeResp(200, _naver_payload()))


def _payload(include_travel):
    return {
        "input": "홍대 저녁 한식 맛집 추천해줘",
        "location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
        "preferences": {"category": "restaurant", "keywords": ["저녁", "한식"]},
        "options": {"include_travel_time": include_travel},
    }


# 9. include_travel_time=false -> Maps (geocode/directions) never called
def test_no_travel_when_flag_false(client, search_ok, monkeypatch):
    monkeypatch.setattr(place_svc.maps, "geocode",
                        lambda a: pytest.fail("geocode must not run when flag is false"))
    r = client.post(RECOMMEND, json=_payload(False))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert all(p["travel"] is None for p in body["data"]["recommended_places"])


# include_travel_time=true (happy path) -> top place gets travel + tag/bonus
def test_travel_included_and_scored(client, search_ok, monkeypatch):
    monkeypatch.setattr(place_svc.maps, "geocode",
                        lambda a: {"latitude": 37.5541, "longitude": 126.9223,
                                   "road_address": a, "jibun_address": None})
    monkeypatch.setattr(place_svc.travel_svc, "safe_compute_travel",
                        lambda *a, **k: {"distance_meters": 3200, "duration_minutes": 12,
                                         "transport_mode": "car",
                                         "route_summary": "자동차 기준 약 12분 소요",
                                         "source": "naver_maps"})
    r = client.post(RECOMMEND, json=_payload(True))
    assert r.status_code == 200
    top = r.json()["data"]["recommended_places"][0]
    assert top["travel"]["duration_minutes"] == 12
    assert any("이동" in t for t in top["recommendation_tags"])
    assert top["score"] <= 100


# 8. Maps failure must NOT fail the whole recommendation
def test_maps_failure_does_not_break_recommendation(client, search_ok, monkeypatch):
    def _boom(addr):
        raise RuntimeError("maps down")
    monkeypatch.setattr(place_svc.maps, "geocode", _boom)
    r = client.post(RECOMMEND, json=_payload(True))
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["recommended_places"]                 # still returned
    assert all(p["travel"] is None for p in body["data"]["recommended_places"])


# --------------------------------------------------------------------------- #
# Travel is ON by default (no options block) when location coords are present.
# --------------------------------------------------------------------------- #
def test_travel_on_by_default(client, search_ok, monkeypatch):
    monkeypatch.setattr(place_svc.maps, "geocode",
                        lambda a: {"latitude": 37.5541, "longitude": 126.9223,
                                   "road_address": a, "jibun_address": None})
    monkeypatch.setattr(place_svc.travel_svc, "safe_compute_travel",
                        lambda *a, **k: {"distance_meters": 3200, "duration_minutes": 12,
                                         "transport_mode": "car",
                                         "route_summary": "약 12분", "source": "naver_maps"})
    payload = {
        "input": "홍대 저녁 한식 맛집 추천해줘",
        "location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
        "preferences": {"category": "restaurant"},
        # NOTE: no "options" block at all -> travel should still be computed
    }
    r = client.post(RECOMMEND, json=payload)
    assert r.status_code == 200
    top = r.json()["data"]["recommended_places"][0]
    assert top["travel"] is not None
    assert top["travel"]["duration_minutes"] == 12


# --------------------------------------------------------------------------- #
# Schedule-aware scoring: comfortable fit gets bonus + "일정 여유" tag.
# --------------------------------------------------------------------------- #
def _schedule_payload(duration_minutes, start, end):
    return {
        "input": "홍대 저녁 한식 맛집 추천해줘",
        "location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
        "preferences": {"category": "restaurant"},
        "schedule_context": {
            "available_start_time": start,
            "available_end_time": end,
            "duration_minutes": duration_minutes,
        },
    }


def _mock_maps(monkeypatch, minutes):
    monkeypatch.setattr(place_svc.maps, "geocode",
                        lambda a: {"latitude": 37.5541, "longitude": 126.9223,
                                   "road_address": a, "jibun_address": None})
    monkeypatch.setattr(place_svc.travel_svc, "safe_compute_travel",
                        lambda *a, **k: {"distance_meters": 3200, "duration_minutes": minutes,
                                         "transport_mode": "car",
                                         "route_summary": f"약 {minutes}분", "source": "naver_maps"})


def test_schedule_comfortable_fit_bonus(client, search_ok, monkeypatch):
    # travel 12 + stay 60 = 72 needed; window 18:00-21:00 = 180; 72 <= 180*0.8 -> comfortable
    _mock_maps(monkeypatch, 12)
    r = client.post(RECOMMEND, json=_schedule_payload(60, "18:00", "21:00"))
    assert r.status_code == 200
    top = r.json()["data"]["recommended_places"][0]
    assert "일정 여유" in top["recommendation_tags"]
    assert top["travel"]["duration_minutes"] == 12


def test_schedule_overflow_penalty(client, search_ok, monkeypatch):
    # travel 40 + stay 90 = 130 needed; window 18:00-19:00 = 60 -> overflow
    _mock_maps(monkeypatch, 40)
    r = client.post(RECOMMEND, json=_schedule_payload(90, "18:00", "19:00"))
    assert r.status_code == 200
    places = r.json()["data"]["recommended_places"]
    tagged = [p for p in places if p["travel"] is not None]
    assert tagged and "일정 초과 우려" in tagged[0]["recommendation_tags"]


def test_schedule_scoring_unit():
    from backend.services.place_recommendation_service import (
        _available_window_minutes, _schedule_usable, _parse_hhmm,
    )
    assert _parse_hhmm("18:30") == 18 * 60 + 30
    assert _parse_hhmm("bad") is None
    assert _available_window_minutes(
        {"available_start_time": "18:00", "available_end_time": "21:00"}) == 180
    # end <= start -> unusable
    assert _available_window_minutes(
        {"available_start_time": "21:00", "available_end_time": "18:00"}) is None
    assert _schedule_usable(
        {"available_start_time": "18:00", "available_end_time": "21:00",
         "duration_minutes": 60}) is True
    # window but no duration -> not usable for schedule scoring
    assert _schedule_usable(
        {"available_start_time": "18:00", "available_end_time": "21:00"}) is False
