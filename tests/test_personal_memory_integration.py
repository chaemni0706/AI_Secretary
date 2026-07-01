"""Personal-memory (preference) integration tests.

Connects stored user preferences to reservation candidates, notification
reminders and emotion coaching. Isolated temp SQLite; no external calls / no
real LLM (rule-based paths only). Base date fixed to 2026-07-01.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

PREF = "/api/v1/memory/local-user/preferences/effective"
RESV = "/api/v1/reservations/business-candidates"
REMIND = "/api/v1/notifications/recommend"
COACH = "/api/v1/emotion/coach"
USER = "local-user"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "pref.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _env(r, *, success=True):
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys())
    assert body["success"] is success
    return body["data"]


def _save_pref(client, **fields):
    return client.put(PREF, json=fields)


def _hour(hhmm):
    return int(hhmm.split(":")[0])


# --------------------------------------------------------------------------- #
# 1. no preference -> default preference, personalization not applied
# --------------------------------------------------------------------------- #
def test_default_preference_when_none_stored(client):
    data = _env(client.get(PREF))
    assert data["personalization_applied"] is False
    assert data["memory_source"] == "default_preference"
    pref = data["preference"]
    assert pref["default_reminder_minutes"] == 30
    assert pref["preferred_reservation_times"] == ["afternoon", "evening"]
    assert pref["late_prone"] is False


# --------------------------------------------------------------------------- #
# 2. partial preference merges over defaults
# --------------------------------------------------------------------------- #
def test_partial_preference_merges_with_defaults(client):
    _save_pref(client, default_reminder_minutes=40)
    pref = _env(client.get(PREF))["preference"]
    assert pref["default_reminder_minutes"] == 40                  # stored
    assert pref["preferred_reservation_times"] == ["afternoon", "evening"]  # default
    assert pref["preferred_tone"] == "neutral"                     # default


# --------------------------------------------------------------------------- #
# 3. invalid values fall back, never 500
# --------------------------------------------------------------------------- #
def test_invalid_preference_values_fall_back(client):
    r = _save_pref(
        client,
        default_reminder_minutes=-5,          # negative -> ignored
        departure_buffer_minutes=-10,         # negative -> ignored
        preferred_tone="weird",               # unknown -> ignored
        preferred_reservation_times=["nonsense", "evening"],  # filter invalid bucket
        notification_style="loud",            # unknown -> ignored
    )
    assert r.status_code in (200, 422)        # must not be 500
    pref = _env(client.get(PREF))["preference"]
    assert pref["default_reminder_minutes"] == 30       # default kept
    assert pref["departure_buffer_minutes"] == 10       # default kept
    assert pref["preferred_tone"] == "neutral"          # default kept
    assert pref["preferred_reservation_times"] == ["evening"]   # only valid bucket kept
    assert pref["notification_style"] == "normal"


# --------------------------------------------------------------------------- #
# 4. evening preference -> evening candidates ranked first
# --------------------------------------------------------------------------- #
def test_reservation_evening_preference_ranks_evening_first(client):
    _save_pref(client, preferred_reservation_times=["evening"])
    data = _env(client.post(RESV, json={
        "user_id": USER, "category": "hair", "date": "2026-07-03",
        "time_preference": "any", "duration_minutes": 60,
    }))
    cands = data["candidates"]
    assert cands, "expected candidates across the day"
    assert 18 <= _hour(cands[0]["start_time"]) < 22        # evening slot first
    assert cands[0]["personalization_score"] >= 0.8


# --------------------------------------------------------------------------- #
# 5. reservation response carries personalization metadata
# --------------------------------------------------------------------------- #
def test_reservation_personalization_metadata_present(client):
    _save_pref(client, preferred_reservation_times=["evening"], late_prone=True)
    data = _env(client.post(RESV, json={
        "user_id": USER, "category": "hair", "date": "2026-07-03",
        "time_preference": "evening", "duration_minutes": 60,
    }))
    meta = data["personalization"]
    assert meta["personalization_applied"] is True
    assert meta["memory_source"] == "stored_preference"
    assert "preferred_reservation_times" in meta["used_preferences"]
    assert "late_prone" in meta["used_preferences"]
    for c in data["candidates"]:
        assert 0.0 <= c["personalization_score"] <= 1.0


# --------------------------------------------------------------------------- #
# 6. late_prone -> earlier (more여유) reminders
# --------------------------------------------------------------------------- #
def test_late_prone_makes_reminders_earlier(client):
    base = _env(client.post(REMIND, json={"user_id": USER, "title": "병원", "start_time": "15:00", "travel_minutes": 30}))
    base_default = next(x for x in base["reminders"] if x["type"] == "default")["minutes_before"]

    _save_pref(client, late_prone=True)
    late = _env(client.post(REMIND, json={"user_id": USER, "title": "병원", "start_time": "15:00", "travel_minutes": 30}))
    late_default = next(x for x in late["reminders"] if x["type"] == "default")["minutes_before"]
    assert late_default > base_default          # late-prone reminded earlier


# --------------------------------------------------------------------------- #
# 7. default_reminder_minutes reflected
# --------------------------------------------------------------------------- #
def test_default_reminder_minutes_reflected(client):
    _save_pref(client, default_reminder_minutes=40)     # late_prone default false
    data = _env(client.post(REMIND, json={"user_id": USER, "title": "병원"}))
    default = next(x for x in data["reminders"] if x["type"] == "default")
    assert default["minutes_before"] == 40
    assert "default_reminder_minutes" in data["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 8. departure_buffer_minutes reflected
# --------------------------------------------------------------------------- #
def test_departure_buffer_minutes_reflected(client):
    _save_pref(client, departure_buffer_minutes=20)     # late_prone default false
    data = _env(client.post(REMIND, json={
        "user_id": USER, "title": "병원", "start_time": "15:00", "travel_minutes": 30,
    }))
    dep = next(x for x in data["reminders"] if x["type"] == "departure")
    assert dep["minutes_before"] == 30 + 20             # travel + buffer
    assert "departure_buffer_minutes" in data["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 9. preferred_tone / coaching_style reflected in coaching message
# --------------------------------------------------------------------------- #
def test_coaching_tone_and_style_reflected(client):
    _save_pref(client, preferred_tone="gentle", coaching_style="supportive")
    data = _env(client.post(COACH, json={"user_id": USER, "text": "요즘 너무 피곤하고 지쳐"}))
    assert data["coaching_message"].startswith("괜찮아요")      # gentle tone prefix
    assert "함께 해봐요" in data["coaching_message"]            # supportive style tail
    assert "preferred_tone" in data["personalization"]["used_preferences"]
    # non-diagnostic guarantee
    assert not any(term in data["coaching_message"] for term in ("우울증", "진단", "장애"))


# --------------------------------------------------------------------------- #
# 10. stress_triggers -> reinforced suggested_actions
# --------------------------------------------------------------------------- #
def test_stress_triggers_boost_actions(client):
    _save_pref(client, stress_triggers=["과제", "마감"])
    data = _env(client.post(COACH, json={"user_id": USER, "text": "과제 마감 때문에 스트레스 받아"}))
    assert "할 일을 작게 나누기" in data["suggested_actions"]
    assert "stress_triggers" in data["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 11. rest_recommendation_enabled=false -> no rest suggestion
# --------------------------------------------------------------------------- #
def test_rest_recommendation_disabled_excludes_rest(client):
    _save_pref(client, rest_recommendation_enabled=False)
    data = _env(client.post(COACH, json={"user_id": USER, "text": "너무 피곤해"}))
    assert not any(("휴식" in a or "쉬" in a or "산책" in a) for a in data["suggested_actions"])


# --------------------------------------------------------------------------- #
# 12. preference round-trip (save -> read matches)
# --------------------------------------------------------------------------- #
def test_preference_round_trip(client):
    _save_pref(
        client,
        preferred_reservation_times=["evening"], default_reminder_minutes=45,
        late_prone=True, preferred_tone="gentle", notification_style="soft",
    )
    pref = _env(client.get(PREF))["preference"]
    assert pref["preferred_reservation_times"] == ["evening"]
    assert pref["default_reminder_minutes"] == 45
    assert pref["late_prone"] is True
    assert pref["preferred_tone"] == "gentle"
    assert pref["notification_style"] == "soft"


# --------------------------------------------------------------------------- #
# robustness: features still work with no preference (fallback), no 500
# --------------------------------------------------------------------------- #
def test_features_work_without_preference(client):
    resv = _env(client.post(RESV, json={
        "user_id": USER, "category": "hair", "date": "2026-07-03",
        "time_preference": "evening", "duration_minutes": 60,
    }))
    assert resv["personalization"]["personalization_applied"] is False
    assert resv["candidates"]                                  # still recommends

    remind = _env(client.post(REMIND, json={"user_id": USER, "title": "병원"}))
    assert remind["reminders"][0]["minutes_before"] == 30      # default
    assert remind["personalization"]["personalization_applied"] is False

    coach = _env(client.post(COACH, json={"user_id": USER, "text": "너무 피곤해"}))
    assert coach["coaching_message"]
    assert coach["personalization"]["personalization_applied"] is False


def test_coach_empty_text_is_422(client):
    r = client.post(COACH, json={"user_id": USER, "text": ""})
    assert r.status_code == 422
