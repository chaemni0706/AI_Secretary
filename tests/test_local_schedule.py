"""Local Schedule CRUD API tests (Stage 4).

Uses an isolated temp SQLite DB via dependency override of get_db (does NOT
import conftest). Verifies the common envelope, CRUD, filters, sorting,
soft-delete exclusion and safe missing-id handling.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

BASE = "/api/v1/local/schedules"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "api_sched.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _create(client, **over):
    body = {"title": "병원 예약", "date": "2026-06-30", "start_time": "14:00",
            "end_time": "15:00", "category": "hospital", "priority": "high",
            "location": "서울OO병원", "memo": "진료", "source": "ai",
            "travel_time_minutes": 30}
    body.update(over)
    r = client.post(BASE, json=body)
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["success"] is True
    assert {"success", "message", "data"}.issubset(env.keys())
    return env["data"]


def test_create_returns_envelope_and_lowercase_fields(client):
    data = _create(client)
    assert data["id"]
    assert data["priority"] == "high"
    assert data["source"] == "ai"
    assert data["status"] == "scheduled"
    assert data["date"] == "2026-06-30" and data["start_time"] == "14:00"


def test_get_list_and_single(client):
    a = _create(client, title="A")
    _create(client, title="B")
    lst = client.get(BASE).json()["data"]
    assert len(lst) == 2
    one = client.get(f"{BASE}/{a['id']}").json()["data"]
    assert one["title"] == "A"


def test_update_schedule(client):
    a = _create(client)
    r = client.patch(f"{BASE}/{a['id']}", json={"title": "수정됨", "priority": "low"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["title"] == "수정됨" and data["priority"] == "low"


def test_delete_excludes_from_list(client):
    a = _create(client, title="A")
    b = _create(client, title="B")
    r = client.delete(f"{BASE}/{a['id']}")
    assert r.status_code == 200 and r.json()["data"]["deleted"] is True
    ids = [s["id"] for s in client.get(BASE).json()["data"]]
    assert a["id"] not in ids and b["id"] in ids


def test_date_filter(client):
    _create(client, date="2026-06-30")
    _create(client, date="2026-07-01")
    out = client.get(BASE, params={"date": "2026-06-30"}).json()["data"]
    assert len(out) == 1 and out[0]["date"] == "2026-06-30"


def test_priority_filter(client):
    _create(client, priority="high")
    _create(client, priority="low")
    out = client.get(BASE, params={"priority": "low"}).json()["data"]
    assert len(out) == 1 and out[0]["priority"] == "low"


def test_list_sorted_by_date_then_start_time(client):
    _create(client, date="2026-07-02", start_time="09:00", end_time=None)
    _create(client, date="2026-07-01", start_time="18:00", end_time=None)
    _create(client, date="2026-07-01", start_time="08:00", end_time=None)
    out = client.get(BASE).json()["data"]
    keys = [(s["date"], s["start_time"]) for s in out]
    assert keys == sorted(keys)
    assert keys[0] == ("2026-07-01", "08:00")


def test_missing_id_returns_404_envelope(client):
    r = client.get(f"{BASE}/nope")
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert client.patch(f"{BASE}/nope", json={"title": "x"}).status_code == 404
    assert client.delete(f"{BASE}/nope").status_code == 404


def test_invalid_end_before_start_returns_422_not_500(client):
    r = client.post(BASE, json={"title": "x", "date": "2026-06-30",
                                "start_time": "15:00", "end_time": "14:00"})
    assert r.status_code == 422
    assert r.json()["success"] is False
    # API still usable afterwards (no wedged transaction)
    ok = client.post(BASE, json={"title": "ok", "date": "2026-06-30", "start_time": "09:00"})
    assert ok.status_code == 200
