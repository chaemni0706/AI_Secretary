"""Tests for the place-recommendation feature (/api/v1/places/recommend).

No real Naver calls: the HTTP layer is mocked via monkeypatch. Covers query
parsing, HTML stripping, scoring clamp/sort, and graceful error handling for
missing credentials and upstream failures.
"""

import httpx
import pytest

from backend.core.config import settings
from backend.services import naver_place_client as naver
from backend.services import place_recommendation_service as svc
from backend.services.place_query_parser import build_search_query, load_place_rules

V1 = "/api/v1"
RECOMMEND = f"{V1}/places/recommend"


# --------------------------------------------------------------------------- #
# Fake Naver HTTP response
# --------------------------------------------------------------------------- #
class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _naver_payload():
    return {
        "items": [
            {
                "title": "<b>홍대</b> 한식당 예시",
                "link": "https://map.naver.com/example1",
                "category": "한식>백반,가정식",
                "telephone": "02-000-0000",
                "address": "서울 마포구 서교동 1-1",
                "roadAddress": "서울 마포구 양화로 100",
                "mapx": "1269245000",
                "mapy": "375572000",
            },
            {
                "title": "무관한 옷가게",
                "link": "",
                "category": "생활,편의>의류",
                "telephone": "",
                "address": "서울 마포구 서교동 2-2",
                "roadAddress": "",
                "mapx": "1269000000",
                "mapy": "375500000",
            },
        ]
    }


@pytest.fixture
def mock_naver_ok(monkeypatch):
    """Patch httpx.get inside the client to return a canned 200 payload."""
    def _fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResp(200, _naver_payload())

    # ensure credentials look present regardless of .env
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(naver.httpx, "get", _fake_get)


# --------------------------------------------------------------------------- #
# 1-3. Query / category parsing
# --------------------------------------------------------------------------- #
def test_parse_restaurant_category():
    query, category = build_search_query("홍대 근처에서 저녁 먹을 만한 곳 추천해줘")
    assert category == "restaurant"
    assert "홍대" in query


def test_parse_cafe_category():
    query, category = build_search_query("건대 카페 추천해줘")
    assert category == "cafe"
    assert "카페" in query


def test_parse_activity_category():
    _, category = build_search_query("강남에서 놀만한 곳 추천해줘")
    assert category == "activity"


def test_explicit_preference_category_wins():
    _, category = build_search_query("아무거나", preferences={"category": "beauty"})
    assert category == "beauty"


# --------------------------------------------------------------------------- #
# 4. HTML tag stripping
# --------------------------------------------------------------------------- #
def test_html_tags_stripped():
    assert naver._strip_html("<b>홍대맛집</b>") == "홍대맛집"
    item = {"title": "<b>홍대</b> 한식당", "category": "한식", "roadAddress": "서울"}
    normalized = naver._normalize(item)
    assert "<" not in normalized["name"] and normalized["name"] == "홍대 한식당"


# --------------------------------------------------------------------------- #
# 5-6. Scoring clamp + sort
# --------------------------------------------------------------------------- #
def test_score_is_clamped_0_100():
    rules = load_place_rules()
    # a place hitting every bonus must not exceed 100
    rich = {
        "name": "저녁 한식 맛집",
        "category": "한식>백반",
        "address": "서울",
        "road_address": "서울 도로명",
        "phone": "02-1",
        "map_url": "http://x",
    }
    score, _, _ = svc._score_place(rich, "restaurant", ["저녁"], "casual", rules)
    assert 0 <= score <= 100

    # a bare place with unknown category must not go below 0
    poor = {"name": "x"}
    score2, _, _ = svc._score_place(poor, None, [], None, rules)
    assert 0 <= score2 <= 100


def test_recommendations_sorted_desc(mock_naver_ok):
    data = svc.recommend_places(
        {"input": "홍대 저녁 한식 맛집 추천해줘", "preferences": {"category": "restaurant"}}
    )
    scores = [p.score for p in data.recommended_places]
    assert scores == sorted(scores, reverse=True)
    # the matching Korean restaurant should outrank the clothing store
    assert data.recommended_places[0].name.startswith("홍대")


# --------------------------------------------------------------------------- #
# 7. Missing credentials -> clear error (no crash)
# --------------------------------------------------------------------------- #
def test_missing_credentials_returns_clear_error(client, monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", None)
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", None)
    r = client.post(RECOMMEND, json={"input": "홍대 저녁 맛집 추천해줘"})
    assert r.status_code == 503
    body = r.json()
    assert body["success"] is False
    assert "네이버" in body["message"]


# --------------------------------------------------------------------------- #
# 8. Upstream failure -> graceful failure response (no 500)
# --------------------------------------------------------------------------- #
def test_upstream_failure_is_handled(client, monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "test-secret")

    def _boom(url, headers=None, params=None, timeout=None):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(naver.httpx, "get", _boom)
    r = client.post(RECOMMEND, json={"input": "홍대 저녁 맛집 추천해줘"})
    assert r.status_code == 502
    body = r.json()
    assert body["success"] is False
    assert body["data"] is None


# --------------------------------------------------------------------------- #
# End-to-end happy path through the API
# --------------------------------------------------------------------------- #
def test_recommend_endpoint_ok(client, mock_naver_ok):
    payload = {
        "user_id": "user-1",
        "input": "홍대 근처에서 저녁 먹을 만한 식당 추천해줘",
        "preferences": {"category": "restaurant", "keywords": ["저녁", "한식"]},
        "schedule_context": {"available_start_time": "18:30", "available_end_time": "21:00"},
    }
    r = client.post(RECOMMEND, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["recommended_places"]
    top = data["recommended_places"][0]
    assert {"place_id", "name", "score", "reason", "recommendation_tags", "source"} <= top.keys()
    assert data["filters"]["available_time"] == "18:30-21:00"
