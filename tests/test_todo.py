"""Local To-do CRUD API tests (Stage 4). Isolated temp DB via get_db override."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

BASE = "/api/v1/local/todos"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "api_todo.db"
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
    body = {"title": "과제", "due_date": "2026-07-01", "priority": "medium",
            "completed": False, "category": "study", "memo": "리포트", "source": "user"}
    body.update(over)
    r = client.post(BASE, json=body)
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["success"] is True
    assert {"success", "message", "data"}.issubset(env.keys())
    return env["data"]


def test_create_and_envelope(client):
    data = _create(client)
    assert data["id"]
    assert data["completed"] is False
    assert data["priority"] == "medium"
    assert data["source"] == "user"
    assert data["due_date"] == "2026-07-01"


def test_get_list_single(client):
    a = _create(client, title="A")
    _create(client, title="B")
    assert len(client.get(BASE).json()["data"]) == 2
    assert client.get(f"{BASE}/{a['id']}").json()["data"]["title"] == "A"


def test_update_and_complete(client):
    a = _create(client)
    r = client.patch(f"{BASE}/{a['id']}", json={"completed": True, "title": "끝"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["completed"] is True and data["status"] == "completed"
    assert data["title"] == "끝"


def test_delete(client):
    a = _create(client)
    assert client.delete(f"{BASE}/{a['id']}").json()["data"]["deleted"] is True
    ids = [t["id"] for t in client.get(BASE).json()["data"]]
    assert a["id"] not in ids


def test_completed_filter(client):
    _create(client, title="open", completed=False)
    _create(client, title="done", completed=True)
    done = client.get(BASE, params={"completed": True}).json()["data"]
    assert len(done) == 1 and done[0]["completed"] is True
    open_ = client.get(BASE, params={"completed": False}).json()["data"]
    assert len(open_) == 1 and open_[0]["completed"] is False


def test_priority_and_completed_sorting(client):
    _create(client, title="low-open", priority="low", completed=False)
    _create(client, title="high-open", priority="high", completed=False)
    _create(client, title="med-done", priority="medium", completed=True)
    out = client.get(BASE).json()["data"]
    # not-completed first; within, high before low
    assert out[0]["title"] == "high-open"
    assert out[1]["title"] == "low-open"
    assert out[-1]["completed"] is True


def test_missing_id_returns_404(client):
    assert client.get(f"{BASE}/nope").status_code == 404
    assert client.patch(f"{BASE}/nope", json={"title": "x"}).status_code == 404
    assert client.delete(f"{BASE}/nope").status_code == 404
