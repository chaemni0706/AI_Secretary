"""Travel-aware departure-plan tests + legacy backward-compat guard.

POST /api/v1/alerts/departure-plan
"""

import pytest

from backend.services import departure_alert as dep

PATH = "/api/v1/alerts/departure-plan"

_TRAVEL_18 = {
    "distance_meters": 3200, "duration_minutes": 18,
    "route_summary": "자동차 기준 약 18분 소요", "transport_mode": "car", "source": "naver_maps",
}


def _travel_request():
    return {
        "user_id": "user-1",
        "current_datetime": "2026-07-03T17:30:00+09:00",
        "timezone": "Asia/Seoul",
        "schedule": {
            "id": "sch_001", "title": "홍대 한식당 방문", "category": "restaurant",
            "date": "2026-07-03", "start_time": "19:00", "end_time": "20:30",
            "location": "서울 마포구 ...", "latitude": 37.5541, "longitude": 126.9223,
            "priority": "medium", "is_fixed": True,
        },
        "user_profile": {
            "default_alert_minutes_before": 30, "departure_buffer_minutes": 10,
            "transport_mode": "car", "late_prone": True,
            "current_location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
        },
        "options": {
            "include_checklist": True, "include_departure_alert": True,
            "include_mock_call_alert": True, "include_travel_time": True, "voice_enabled": True,
        },
    }


@pytest.fixture
def mock_travel(monkeypatch):
    monkeypatch.setattr(dep.travel_svc, "safe_compute_travel",
                        lambda *a, **k: dict(_TRAVEL_18))


# 7. travel 18 + buffer 10 + start 19:00 -> departure 18:32, trigger 18:22
def test_departure_time_computed_from_travel(client, mock_travel):
    r = client.post(PATH, json=_travel_request())
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    plan = body["data"]["alert_plan"]
    assert body["data"]["schedule_id"] == "sch_001"
    assert plan["travel"]["duration_minutes"] == 18
    rem = plan["reminders"][0]
    assert rem["departure_time"] == "18:32"                     # 19:00 - 18 - 10
    assert rem["trigger_datetime"] == "2026-07-03T18:22:00+09:00"   # departure - 10
    assert plan["voice_alert_text"]                              # voice_enabled


# travel unavailable -> falls back to default_alert_minutes_before (no crash)
def test_fallback_when_no_travel(client, monkeypatch):
    monkeypatch.setattr(dep.travel_svc, "safe_compute_travel", lambda *a, **k: None)
    req = _travel_request()
    req["schedule"]["latitude"] = None
    req["schedule"]["longitude"] = None
    r = client.post(PATH, json=req)
    assert r.status_code == 200
    plan = r.json()["data"]["alert_plan"]
    assert plan["travel"] is None
    assert plan["reminders"][0]["departure_time"] == "18:30"    # 19:00 - 30 (default)


# 8-legacy. Legacy request (no options) still returns the original contract.
def test_legacy_contract_unchanged(client):
    r = client.post(PATH, json={
        "schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00"},
        "context": {"weather": "rain", "estimated_travel_minutes": 35, "buffer_minutes": 10},
        "user_preference": {"notification_style": "normal"},
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) == {
        "leave_time", "estimated_travel_minutes", "buffer_minutes",
        "checklist", "notifications",
    }
    assert data["leave_time"] == "13:15"
