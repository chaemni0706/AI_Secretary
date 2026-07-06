"""End-to-end proof that the AI voice-style setting changes the ACTUAL response.

Exercises the real endpoints the tablet uses:
  * POST /api/v1/ai/schedule/parse  (chat / voice-schedule spoken tts_text)
  * POST /api/v1/ai/schedule/confirm (reminder plan) — with a temp DB.

Same input, different assistant_tone/response_length/reminder_strength ->
different tts_text / reminder count. Legacy calls (no style fields) unchanged.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

PARSE = "/api/v1/ai/schedule/parse"
CONFIRM = "/api/v1/ai/schedule/confirm"
NOW = "2026-06-29T10:00:00+09:00"
TEXT = "내일 3시에 회의 잡아줘"


def _parse(client, **style):
    body = {"input": TEXT, "input_type": "voice", "current_datetime": NOW}
    body.update(style)
    r = client.post(PARSE, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]["tts_text"]


# --------------------------------------------------------------------------- #
# Scenario A/B/C — tone & length change the spoken tts_text
# --------------------------------------------------------------------------- #
def test_no_style_is_legacy_unchanged():
    with TestClient(app) as c:
        assert _parse(c) == "회의 일정을 2026-06-30 15:00으로 정리했어요. 등록할까요?"


def test_tone_changes_response():
    with TestClient(app) as c:
        friendly = _parse(c, assistant_tone="friendly", response_length="medium")
        formal = _parse(c, assistant_tone="formal", response_length="medium")
        caring = _parse(c, assistant_tone="caring", response_length="medium")
        concise = _parse(c, assistant_tone="concise", response_length="medium")
    # all four are different from each other
    assert len({friendly, formal, caring, concise}) == 4
    assert "좋아요" in friendly
    assert "등록했습니다" in formal or "등록하겠습니다" in formal
    assert "챙겨" in caring


def test_length_changes_response():
    with TestClient(app) as c:
        short = _parse(c, assistant_tone="caring", response_length="short")
        long = _parse(c, assistant_tone="caring", response_length="long")
    assert len(short) < len(long)


# --------------------------------------------------------------------------- #
# Scenario D — reminder_strength changes reminder COUNT (1 / 2 / 3)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "style.db"
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


def _confirm_reminder_count(client, strength):
    body = {
        "user_id": "local-user",
        "item_type": "EVENT",
        "parsed": {
            "title": "회의", "date": "2026-07-02", "start_time": "15:00",
            "category": "meeting", "is_all_day": False,
        },
        "reminder_strength": strength,
    }
    r = client.post(CONFIRM, json=body)
    assert r.status_code == 200, r.text
    reminders = r.json()["data"]["reminder_plan"]["reminders"]
    return sum(1 for x in reminders if x["type"] == "reminder")


def test_reminder_strength_changes_count(db_client):
    assert _confirm_reminder_count(db_client, "gentle") == 1
    assert _confirm_reminder_count(db_client, "normal") == 2
    assert _confirm_reminder_count(db_client, "strong") == 3


def test_confirm_without_strength_adds_no_strength_reminders(db_client):
    body = {
        "user_id": "local-user", "item_type": "EVENT",
        "parsed": {"title": "회의", "date": "2026-07-02", "start_time": "15:00",
                   "category": "meeting", "is_all_day": False},
    }
    r = db_client.post(CONFIRM, json=body)
    assert r.status_code == 200, r.text
    reminders = r.json()["data"]["reminder_plan"]["reminders"]
    assert not any(x["type"] == "reminder" for x in reminders)  # default plan unchanged
