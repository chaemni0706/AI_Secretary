"""Reservation candidate -> reservation message integration tests.

Connects a recommended candidate to the EXISTING template+LLM message engine.
Draft-only (no external send / no booking). No real LLM (no API key -> template).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.schema.reservation_message_schema import (
    CandidateInput,
    FromCandidateRequest,
)
from backend.main import app
from backend.services.reservation_message_service import (
    reservation_candidate_to_message_request,
    reservation_type_for,
)

client = TestClient(app)
FROM_CAND = "/api/v1/reservations/message/from-candidate"
CANDS = "/api/v1/reservations/business-candidates"


def _cand(**over):
    base = {"business_id": "hair_001", "business_name": "챔니 헤어살롱", "category": "hair",
            "date": "2026-07-03", "start_time": "18:00", "end_time": "19:00", "duration_minutes": 60}
    base.update(over)
    return base


def _post(payload):
    r = client.post(FROM_CAND, json=payload)
    return r


# --------------------------------------------------------------------------- #
# 1-3. candidate -> message request conversion + category mapping
# --------------------------------------------------------------------------- #
def test_candidate_to_message_request_conversion():
    req = reservation_candidate_to_message_request(
        CandidateInput(business_name="챔니 헤어살롱", category="hair",
                       date="2026-07-03", start_time="18:00"))
    assert req.reservation_info.category == "beauty"        # hair -> beauty engine cat
    assert req.reservation_info.target_date == "2026-07-03"
    assert req.reservation_info.preferred_time == "18:00"


def test_hair_maps_to_beauty():
    assert reservation_type_for("hair") == "beauty"
    assert reservation_type_for("nail") == "beauty"


def test_health_maps_to_hospital():
    assert reservation_type_for("health") == "hospital"
    assert reservation_type_for("hospital") == "hospital"
    assert reservation_type_for("dental") == "hospital"


# --------------------------------------------------------------------------- #
# 4. restaurant party_size reflected in message
# --------------------------------------------------------------------------- #
def test_restaurant_party_size_in_message():
    body = _post({"candidate": _cand(business_name="한상 다이닝", category="restaurant"),
                  "party_size": 4, "service_name": "저녁 식사"}).json()
    assert body["success"] is True
    assert "4명" in body["data"]["message_card"]["message_text"]
    assert body["data"]["message_card"]["reservation_type"] == "restaurant"


# --------------------------------------------------------------------------- #
# 5. beauty default '커트 또는 시술' kept when no service_name
# --------------------------------------------------------------------------- #
def test_beauty_default_service_phrase():
    body = _post({"candidate": _cand()}).json()
    assert "커트 또는 시술" in body["data"]["message_card"]["message_text"]
    assert body["data"]["message_card"]["reservation_type"] == "beauty"


# --------------------------------------------------------------------------- #
# 6-10. message_card structure + delivery + source_candidate
# --------------------------------------------------------------------------- #
def test_message_card_returned():
    body = _post({"candidate": _cand()}).json()
    assert "message_card" in body["data"]
    card = body["data"]["message_card"]
    assert card["action_type"] == "inquiry"
    assert card["business_name"] == "챔니 헤어살롱"


def test_message_text_and_copy_text_present():
    card = _post({"candidate": _cand()}).json()["data"]["message_card"]
    assert card["message_text"] and card["copy_text"]
    assert card["copy_text"] == card["message_text"]


def test_delivery_is_draft_only():
    card = _post({"candidate": _cand()}).json()["data"]["message_card"]
    assert card["delivery"]["external_send_enabled"] is False
    assert card["delivery"]["status"] == "draft_only"


def test_source_candidate_included():
    data = _post({"candidate": _cand()}).json()["data"]
    src = data["source_candidate"]
    assert src["business_id"] == "hair_001"
    assert src["date"] == "2026-07-03" and src["start_time"] == "18:00"


# --------------------------------------------------------------------------- #
# 11. missing required fields -> 422 + missing_fields (never 500)
# --------------------------------------------------------------------------- #
def test_missing_fields_returns_422():
    r = _post({"candidate": {"category": "hair"}})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert set(body["data"]["missing_fields"]) == {"business_name", "date", "start_time"}


def test_generation_source_present():
    card = _post({"candidate": _cand()}).json()["data"]["message_card"]
    assert card["generation_source"] in ("template", "llm_fallback")


# --------------------------------------------------------------------------- #
# action types: confirm/change/cancel/check
# --------------------------------------------------------------------------- #
def test_action_types_produce_distinct_messages():
    msgs = {}
    for action in ("inquiry", "confirm", "change", "cancel", "check"):
        card = _post({"candidate": _cand(), "action_type": action}).json()["data"]["message_card"]
        assert card["action_type"] == action
        assert card["message_text"]
        msgs[action] = card["message_text"]
    assert len(set(msgs.values())) >= 4          # meaningfully different


def test_invalid_action_type_is_422():
    r = _post({"candidate": _cand(), "action_type": "book_now"})
    assert r.status_code == 422                   # enum validation


# --------------------------------------------------------------------------- #
# 14. candidates response carries next_actions but keeps candidate fields
# --------------------------------------------------------------------------- #
def test_candidates_next_actions_and_fields_preserved(tmp_path):
    from sqlalchemy.orm import sessionmaker
    from backend.database.init_db import apply_schema_to_sqlite_file
    from backend.database.session import create_sqlite_engine, get_db

    db_file = tmp_path / "rc.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TS = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _ov():
        db = TS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _ov
    try:
        with TestClient(app) as c:
            data = c.post(CANDS, json={"user_id": "local-user", "category": "hair",
                                       "date": "2026-07-03", "time_preference": "evening",
                                       "duration_minutes": 60}).json()["data"]
        assert data["next_actions"]
        assert data["next_actions"][0]["type"] == "generate_message"
        cand = data["candidates"][0]
        for f in ("business_id", "business_name", "date", "start_time", "end_time"):
            assert f in cand                       # candidate fields preserved
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
