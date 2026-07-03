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
