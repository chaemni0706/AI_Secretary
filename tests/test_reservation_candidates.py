"""Virtual-business reservation tests (mock layer).

Covers the business-aware recommender + booking:
  POST /api/v1/reservations/business-candidates
  GET  /api/v1/reservations/businesses[/{id}]
  POST /api/v1/reservations/book

Isolated temp SQLite DB via get_db override (does NOT import conftest), mirroring
tests/test_reservation_from_store.py. Seed data lives in
backend/rules/virtual_businesses.json. 2026-07-03 is a Friday; 2026-07-06 a Monday.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

CAND = "/api/v1/reservations/business-candidates"
BOOK = "/api/v1/reservations/book"
BIZ = "/api/v1/reservations/businesses"
LOCAL = "/api/v1/local/schedules"

FRI = "2026-07-03"
MON = "2026-07-06"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "resv_cand.db"
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


def _min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def _overlaps(cand, b_start, b_end) -> bool:
    s, e = _min(cand["start_time"]), _min(cand["end_time"])
    return s < _min(b_end) and _min(b_start) < e


def _cands(client, **body):
    body.setdefault("category", "hair")
    body.setdefault("date", FRI)
    r = client.post(CAND, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _seed_local(client, *, start, end, title="내 일정", date=FRI):
    r = client.post(LOCAL, json={"title": title, "date": date,
                                 "start_time": start, "end_time": end})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_envelope_and_shape(client):
    body = _cands(client, time_preference="evening", duration_minutes=60)
    assert {"success", "message", "data"}.issubset(body.keys())
    data = body["data"]
    assert set(data.keys()) == {"requested", "candidates", "alternatives"}
    assert data["requested"]["category"] == "hair"
    cand = data["candidates"][0]
    assert set(cand.keys()) == {
        "business_id", "business_name", "category", "date",
        "start_time", "end_time", "reason",
    }


# --------------------------------------------------------------------------- #
# 1. candidates are generated inside operating hours + preferred window
# --------------------------------------------------------------------------- #
def test_candidates_within_operating_hours(client):
    data = _cands(client, time_preference="evening", duration_minutes=60)["data"]
    cands = data["candidates"]
    assert len(cands) >= 1
    for c in cands:
        # evening window 18:00~21:00, and hair shops close by 20:00/21:00
        assert 18 * 60 <= _min(c["start_time"])
        assert _min(c["end_time"]) <= 21 * 60
        assert _min(c["end_time"]) > _min(c["start_time"])
    # earliest-first ordering
    starts = [_min(c["start_time"]) for c in cands]
    assert starts == sorted(starts)
    assert cands[0]["start_time"] == "18:00"   # hair_002 opens the evening


# --------------------------------------------------------------------------- #
# 2. business reserved_slots are excluded
# --------------------------------------------------------------------------- #
def test_reserved_slots_excluded(client):
    # hair_001 evening: reserved 18:00~19:00 -> only 19:00~20:00 is free
    data = _cands(client, business_id="hair_001",
                  time_preference="evening", duration_minutes=60)["data"]
    cands = data["candidates"]
    assert cands, "expected the free 19:00 slot"
    assert all(not _overlaps(c, "18:00", "19:00") for c in cands)
    assert any(c["start_time"] == "19:00" and c["end_time"] == "20:00" for c in cands)


# --------------------------------------------------------------------------- #
# 3. user's existing schedule is excluded
# --------------------------------------------------------------------------- #
def test_user_schedule_excluded(client):
    # block hair_001's only free evening slot with a personal schedule
    _seed_local(client, start="19:00", end="20:00", title="저녁 약속")
    data = _cands(client, business_id="hair_001",
                  time_preference="evening", duration_minutes=60)["data"]
    assert all(not _overlaps(c, "19:00", "20:00") for c in data["candidates"])
    # 19:00 was the only option -> no candidates remain for hair_001
    assert data["candidates"] == []


# --------------------------------------------------------------------------- #
# 4. closed day yields no candidates
# --------------------------------------------------------------------------- #
def test_closed_day_returns_no_candidates(client):
    # hair_001 is closed on MON; 2026-07-06 is a Monday
    data = _cands(client, business_id="hair_001", date=MON,
                  time_preference="any", duration_minutes=60)["data"]
    assert data["candidates"] == []


# --------------------------------------------------------------------------- #
# 5. duration 60 correctly occupies two 30-min slots (grid handling)
# --------------------------------------------------------------------------- #
def test_duration_60_spans_two_30min_slots(client):
    # hospital_001 morning (09:00~12:00), reserved 10:00~10:30 (a 30-min block)
    data = _cands(client, category="hospital", business_id="hospital_001",
                  time_preference="morning", duration_minutes=60)["data"]
    cands = data["candidates"]
    assert cands
    # a 60-min slot = two consecutive 30-min slots
    for c in cands:
        assert _min(c["end_time"]) - _min(c["start_time"]) == 60
    # 09:00~10:00 fits before the reserved block
    assert any(c["start_time"] == "09:00" and c["end_time"] == "10:00" for c in cands)
    # nothing may straddle the 30-min reserved block (e.g. 09:30~10:30 is illegal)
    assert all(not _overlaps(c, "10:00", "10:30") for c in cands)


# --------------------------------------------------------------------------- #
# 6. no candidates -> alternatives are offered
# --------------------------------------------------------------------------- #
def test_alternatives_when_no_candidate(client):
    # 180-min service can't fit any hair shop's fragmented evening window
    body = _cands(client, time_preference="evening", duration_minutes=180)
    data = body["data"]
    assert data["candidates"] == []
    assert data["alternatives"], "expected fallback suggestions"
    prefs = {a["time_preference"] for a in data["alternatives"]}
    assert "afternoon" in prefs        # afternoon can fit 180 min (15:00~18:00)
    assert body["message"].endswith("대체 시간대를 안내합니다.")


# --------------------------------------------------------------------------- #
# 7. book a chosen candidate -> saved into local schedule store
# --------------------------------------------------------------------------- #
def test_book_persists_local_schedule(client):
    payload = {
        "user_id": "local-user", "business_id": "hair_001",
        "business_name": "챔니 헤어살롱", "category": "hair",
        "date": FRI, "start_time": "19:00", "end_time": "20:00",
        "memo": "예약 후보 추천에서 선택한 일정",
    }
    r = client.post(BOOK, json=payload)
    assert r.status_code == 200, r.text
    saved = r.json()["data"]["schedule"]
    assert saved["id"]
    assert saved["title"] == "챔니 헤어살롱 예약"
    assert saved["date"] == FRI
    assert saved["start_time"] == "19:00" and saved["end_time"] == "20:00"
    assert saved["category"] == "hair"

    # it must now appear in the local schedule list
    listed = client.get(f"{LOCAL}?date={FRI}").json()["data"]
    assert any(s["id"] == saved["id"] for s in listed)


def test_book_then_slot_is_no_longer_recommended(client):
    # full loop: booking 19:00 removes hair_001's only free evening slot
    before = _cands(client, business_id="hair_001",
                    time_preference="evening", duration_minutes=60)["data"]
    assert any(c["start_time"] == "19:00" for c in before["candidates"])

    client.post(BOOK, json={
        "business_id": "hair_001", "business_name": "챔니 헤어살롱",
        "category": "hair", "date": FRI, "start_time": "19:00", "end_time": "20:00",
    })
    after = _cands(client, business_id="hair_001",
                   time_preference="evening", duration_minutes=60)["data"]
    assert all(c["start_time"] != "19:00" for c in after["candidates"])


def test_book_invalid_time_is_422(client):
    r = client.post(BOOK, json={
        "business_id": "hair_001", "business_name": "챔니 헤어살롱",
        "category": "hair", "date": FRI, "start_time": "20:00", "end_time": "19:00",
    })
    assert r.status_code == 422
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# Catalog endpoints + safety
# --------------------------------------------------------------------------- #
def test_list_businesses(client):
    data = client.get(BIZ).json()["data"]
    assert len(data) >= 6
    ids = {b["business_id"] for b in data}
    assert {"hair_001", "hospital_001", "nail_001"}.issubset(ids)


def test_list_businesses_category_filter(client):
    data = client.get(f"{BIZ}?category=hair").json()["data"]
    assert data and all(b["category"] == "hair" for b in data)


def test_get_business_by_id(client):
    body = client.get(f"{BIZ}/hair_001").json()
    assert body["success"] is True
    assert body["data"]["name"] == "챔니 헤어살롱"


def test_get_unknown_business_404(client):
    r = client.get(f"{BIZ}/nope_999")
    assert r.status_code == 404
    assert r.json()["success"] is False


def test_duration_zero_is_safe(client):
    body = _cands(client, time_preference="evening", duration_minutes=0)
    assert body["success"] is True
    assert body["data"]["candidates"] == []


def test_unknown_category_is_safe(client):
    body = _cands(client, category="unknown_cat", time_preference="any")
    assert body["success"] is True
    assert body["data"]["candidates"] == []
