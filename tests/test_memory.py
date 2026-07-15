"""Personal memory / user-preference API tests (Stage 7).

Backed by user_memories. Isolated temp DB via get_db override; does not import
conftest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.models import User, UserMemory
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

U = "user-123"
BASE = f"/api/v1/memory/{U}"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "mem.db"
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


# --------------------------------------------------------------------------- #
# Unknown user -> defaults (no write)
# --------------------------------------------------------------------------- #
def test_unknown_user_returns_defaults(client):
    data = client.get(BASE).json()["data"]
    assert data["user_id"] == U
    assert data["notification_preference"] == "normal"
    assert data["default_travel_minutes"] == 30
    assert data["default_buffer_minutes"] == 10
    assert data["preferred_transport"] == "public_transport"
    assert data["frequently_visited_places"] == []
    assert data["updated_at"] is None  # nothing stored


# --------------------------------------------------------------------------- #
# notification_preference update
# --------------------------------------------------------------------------- #
def test_update_notification_preference(client):
    r = client.patch(f"{BASE}/preferences", json={"notification_preference": "late_prone"})
    assert r.status_code == 200
    assert r.json()["data"]["notification_preference"] == "late_prone"
    # persisted
    assert client.get(BASE).json()["data"]["notification_preference"] == "late_prone"


def test_invalid_notification_preference_returns_422(client):
    r = client.patch(f"{BASE}/preferences", json={"notification_preference": "panic"})
    assert r.status_code == 422 and r.json()["success"] is False


# --------------------------------------------------------------------------- #
# travel / buffer minutes update
# --------------------------------------------------------------------------- #
def test_update_travel_and_buffer_minutes(client):
    client.patch(f"{BASE}/preferences", json={"default_travel_minutes": 45, "default_buffer_minutes": 15})
    data = client.get(BASE).json()["data"]
    assert data["default_travel_minutes"] == 45
    assert data["default_buffer_minutes"] == 15


def test_negative_minutes_clamped_to_zero(client):
    client.patch(f"{BASE}/preferences", json={"default_travel_minutes": -10})
    assert client.get(BASE).json()["data"]["default_travel_minutes"] == 0


# --------------------------------------------------------------------------- #
# PUT upsert (full-ish) + invalid transport
# --------------------------------------------------------------------------- #
def test_put_upsert(client):
    r = client.put(BASE, json={
        "notification_preference": "strong",
        "preferred_transport": "car",
        "home_location": "서울시 강남구",
        "checklist_preferences": ["우산", "지갑"],
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["notification_preference"] == "strong"
    assert data["preferred_transport"] == "car"
    assert data["home_location"] == "서울시 강남구"
    assert data["checklist_preferences"] == ["우산", "지갑"]


def test_invalid_transport_returns_422(client):
    r = client.put(BASE, json={"preferred_transport": "teleport"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# frequently visited places
# --------------------------------------------------------------------------- #
def test_add_places(client):
    client.post(f"{BASE}/places", json={"name": "회사", "address": "테헤란로", "category": "work"})
    data = client.post(f"{BASE}/places", json={"name": "헬스장", "category": "exercise"}).json()["data"]
    places = data["frequently_visited_places"]
    assert len(places) == 2
    assert {p["name"] for p in places} == {"회사", "헬스장"}


# --------------------------------------------------------------------------- #
# context conversion (alert/reservation)
# --------------------------------------------------------------------------- #
def test_context_conversion(client):
    client.patch(f"{BASE}/preferences", json={
        "notification_preference": "late_prone",
        "default_travel_minutes": 40,
        "default_buffer_minutes": 5,
        "preferred_transport": "public_transport",
    })
    ctx = client.get(f"{BASE}/context").json()["data"]
    assert ctx["notification_preference"] == "late_prone"
    assert ctx["default_travel_minutes"] == 40
    assert ctx["default_buffer_minutes"] == 5
    # mapping to alert UserPreference fields
    pref = ctx["alert_user_preference"]
    assert pref == {"notification_style": "normal", "forgetful": False, "late_prone": True}


def test_context_forgetful_mapping(client):
    client.patch(f"{BASE}/preferences", json={"notification_preference": "forgetful"})
    pref = client.get(f"{BASE}/context").json()["data"]["alert_user_preference"]
    assert pref == {"notification_style": "normal", "forgetful": True, "late_prone": False}


# --------------------------------------------------------------------------- #
# Stage 7.1 — empty PUT/PATCH is a no-op (no junk user / memory rows)
# --------------------------------------------------------------------------- #
def _counts(client):
    """Inspect the test DB directly via the override's session factory."""
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        users = db.query(User).filter(User.user_id == U).count()
        mems = db.query(UserMemory).filter(UserMemory.user_id == U).count()
        return users, mems
    finally:
        gen.close()


def test_empty_put_does_not_create_user_row(client):
    r = client.put(BASE, json={})
    assert r.status_code == 200
    assert r.json()["data"]["user_id"] == U          # defaults still returned
    users, mems = _counts(client)
    assert users == 0 and mems == 0                   # nothing persisted


def test_empty_patch_does_not_create_user_row(client):
    r = client.patch(f"{BASE}/preferences", json={})
    assert r.status_code == 200
    users, mems = _counts(client)
    assert users == 0 and mems == 0


def test_empty_write_preserves_existing_values(client):
    client.patch(f"{BASE}/preferences", json={"notification_preference": "strong"})
    # empty PUT and empty PATCH must not wipe or duplicate anything
    client.put(BASE, json={})
    client.patch(f"{BASE}/preferences", json={})
    data = client.get(BASE).json()["data"]
    assert data["notification_preference"] == "strong"


def test_repeated_update_keeps_single_active_row(client):
    for v in ("normal", "strong", "late_prone", "forgetful"):
        client.patch(f"{BASE}/preferences", json={"notification_preference": v})
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        rows = db.query(UserMemory).filter(
            UserMemory.user_id == U,
            UserMemory.memory_key == "notification_preference",
            UserMemory.is_active == 1,
        ).all()
    finally:
        gen.close()
    assert len(rows) == 1
    assert rows[0].memory_value_masked == "forgetful"
