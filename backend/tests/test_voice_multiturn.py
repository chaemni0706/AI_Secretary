"""voice_route_orchestrator — 멀티턴(슬롯 채우기 + 직전 일정 수정) 통합 테스트.

임시 SQLite로 /api/v1/voice/route 를 실제 호출하며, 응답 context 를 다음 턴에
그대로 되돌려 pendingContext 흐름을 검증한다.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.services import voice_route_orchestrator as O

ROUTE = "/api/v1/voice/route"
NOW = "2026-07-01T10:00:00+09:00"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "v.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _route(client, text, context=None):
    payload = {"text": text, "current_datetime": NOW, "timezone": "Asia/Seoul"}
    if context is not None:
        payload["context"] = context
    r = client.post(ROUTE, json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_slot_fill_then_register(client):
    d1 = _route(client, "내일 병원 예약 잡아줘")
    assert d1["context"]["type"] == "schedule_pending"
    assert "time" in d1["context"]["missing"]

    d2 = _route(client, "오후 3시", context=d1["context"])
    assert d2["context"]["type"] == "schedule_created"
    assert d2["data"]["item"]["start_time"] == "15:00"
    assert "추가했어요" in d2["tts_text"]


def test_modify_existing_with_concrete_time(client):
    d1 = _route(client, "내일 오후 2시 회의 잡아줘")
    assert d1["context"]["type"] == "schedule_created"

    d2 = _route(client, "저녁 7시로 바꿔줘", context=d1["context"])
    assert d2["data"]["item"]["start_time"] == "19:00"
    assert "바꿨어요" in d2["tts_text"]


def test_reminder_reply_not_hijacked_by_modify(client):
    d1 = _route(client, "내일 오후 2시 회의 잡아줘")
    assert d1["context"]["type"] == "schedule_created"
    # 수정 신호가 없으므로 알림 응답은 그대로 reminder 로 처리
    d2 = _route(client, "응 알림 받을래", context=d1["context"])
    assert d2["intent"] == "reminder_setting"


def test_modify_vague_uses_llm(client, monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_MULTITURN", True)
    monkeypatch.setattr(O.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(O.llm_service, "generate_json",
                        lambda *a, **k: {"date": None, "start_time": "15:00"})
    d1 = _route(client, "내일 오전 9시 회의 잡아줘")
    assert d1["context"]["type"] == "schedule_created"

    d2 = _route(client, "아까 그거 오후로 바꿔줘", context=d1["context"])
    assert d2["data"]["item"]["start_time"] == "15:00"
    assert "바꿨어요" in d2["tts_text"]
