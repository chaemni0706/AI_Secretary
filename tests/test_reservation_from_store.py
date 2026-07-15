"""Stored-schedule reservation candidate tests (Stage 9).

Seeds schedules via the local API, then checks /reservations/candidates/from-store.
Reuses the existing recommender; does not touch /reservations/candidates.
Isolated temp DB via get_db override; does not import conftest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.models import Calendar, EventDetail, PlannerItem, User
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

SB = "/api/v1/local/schedules"
STORE = "/api/v1/reservations/candidates/from-store"
DATE = "2026-07-03"
NOW = "2026-07-03T09:00:00"


@pytest.fixture()
def ctx(tmp_path):
    db_file = tmp_path / "rfs.db"
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
        yield c, TestingSession
    app.dependency_overrides.clear()
    engine.dispose()


def _mk(client, *, start, end, title="일정"):
    r = client.post(SB, json={"title": title, "date": DATE, "start_time": start, "end_time": end})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _store(client, **body):
    body.setdefault("target_date", DATE)
    return client.post(STORE, json=body)


def _overlaps(cand, b_start, b_end):
    s = int(cand["start_time"][:2]) * 60 + int(cand["start_time"][3:])
    e = int(cand["end_time"][:2]) * 60 + int(cand["end_time"][3:])
    bs = int(b_start[:2]) * 60 + int(b_start[3:])
    be = int(b_end[:2]) * 60 + int(b_end[3:])
    return s < be and bs < e


# --------------------------------------------------------------------------- #
# basic: candidates avoid the stored busy interval
# --------------------------------------------------------------------------- #
def test_candidates_avoid_stored_event(ctx):
    client, _ = ctx
    _mk(client, start="14:00", end="15:00")
    r = _store(client, duration_minutes=60, preferred_start_time="09:00", preferred_end_time="21:00")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["target_date"] == DATE
    assert data["recommended_candidates"]
    assert all(not _overlaps(c, "14:00", "15:00") for c in data["recommended_candidates"])


# --------------------------------------------------------------------------- #
# no stored schedules -> candidates still generated
# --------------------------------------------------------------------------- #
def test_no_stored_schedules_generates_candidates(ctx):
    client, _ = ctx
    r = _store(client, duration_minutes=60, preferred_start_time="14:00", preferred_end_time="15:00")
    data = r.json()["data"]
    assert len(data["recommended_candidates"]) == 1
    assert data["recommended_candidates"][0]["start_time"] == "14:00"


# --------------------------------------------------------------------------- #
# cancelled event is excluded from busy
# --------------------------------------------------------------------------- #
def test_cancelled_event_not_busy(ctx):
    client, _ = ctx
    sid = _mk(client, start="14:00", end="15:00")
    # window == the busy slot: active -> no candidate; cancelled -> one candidate
    active = _store(client, duration_minutes=60,
                    preferred_start_time="14:00", preferred_end_time="15:00").json()["data"]
    assert active["recommended_candidates"] == []

    client.patch(f"{SB}/{sid}", json={"status": "cancelled"})
    after = _store(client, duration_minutes=60,
                   preferred_start_time="14:00", preferred_end_time="15:00").json()["data"]
    assert len(after["recommended_candidates"]) == 1
    assert after["recommended_candidates"][0]["start_time"] == "14:00"


# --------------------------------------------------------------------------- #
# malformed stored time is skipped (no crash)
# --------------------------------------------------------------------------- #
def test_malformed_event_time_skipped(ctx):
    client, Session = ctx
    db = Session()
    try:
        db.add(User(user_id="local-user", created_at=NOW, updated_at=NOW)); db.commit()
        db.add(Calendar(calendar_id="cx", user_id="local-user", name="c",
                        is_primary=1, created_at=NOW, updated_at=NOW)); db.commit()
        db.add(PlannerItem(item_id="bad", user_id="local-user", item_type="EVENT",
                           title="깨짐", status="SCHEDULED", priority="MEDIUM",
                           source_type="MANUAL", created_at=NOW, updated_at=NOW)); db.commit()
        db.add(EventDetail(item_id="bad", calendar_id="cx", start_at=f"{DATE}xINVALID")); db.commit()
    finally:
        db.close()
    r = _store(client, duration_minutes=60, preferred_start_time="14:00", preferred_end_time="15:00")
    assert r.status_code == 200
    # malformed row ignored -> the 14:00 slot is free
    assert len(r.json()["data"]["recommended_candidates"]) == 1


# --------------------------------------------------------------------------- #
# user preference buffer reflection
# --------------------------------------------------------------------------- #
def test_preference_buffer_blocks_adjacent_slots(ctx):
    client, _ = ctx
    _mk(client, start="14:00", end="15:00")
    client.patch("/api/v1/memory/u1/preferences", json={"default_buffer_minutes": 30})
    base = dict(duration_minutes=60, preferred_start_time="13:00", preferred_end_time="16:00")

    without = _store(client, **base).json()["data"]
    assert len(without["recommended_candidates"]) >= 1   # 13:00 and/or 15:00 free

    with_buf = _store(client, user_id="u1", apply_preference_buffer=True, **base).json()["data"]
    # busy padded to 13:30-15:30 -> only 30-min gaps remain, none fit 60 min
    assert with_buf["recommended_candidates"] == []
