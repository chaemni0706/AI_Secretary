"""Reservation candidate recommendation tests.

POST /api/v1/reservations/candidates

Response field names are part of the frontend contract and must stay stable:
data.target_date / data.recommended_candidates / data.rejected_slots and
each candidate's candidate_id / start_time / end_time / score / reason /
conflict.
"""

PATH = "/api/v1/reservations/candidates"
DATE = "2026-07-03"


def _sched(sid, start, end, title="기존 일정", date=DATE):
    return {"id": sid, "title": title, "date": date,
            "start_time": start, "end_time": end}


def _post(client, existing, **constraint_overrides):
    constraints = {
        "target_date": DATE,
        "preferred_start_time": "18:00",
        "preferred_end_time": "21:00",
        "duration_minutes": 60,
        "category": "beauty",
    }
    constraints.update(constraint_overrides)
    r = client.post(PATH, json={"constraints": constraints, "existing_schedules": existing})
    assert r.status_code == 200
    return r.json()


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    body = _post(client, [])
    assert body["success"] is True
    data = body["data"]
    assert set(data.keys()) == {"target_date", "recommended_candidates", "rejected_slots"}
    assert data["target_date"] == DATE
    cand = data["recommended_candidates"][0]
    assert set(cand.keys()) == {
        "candidate_id", "start_time", "end_time", "score", "reason", "conflict"
    }


# --------------------------------------------------------------------------- #
# 1. 18:00~19:00 팀플, 20:00~21:00 약속 -> 19:00~20:00 추천
# --------------------------------------------------------------------------- #
def test_case1_gap_between_schedules(client):
    body = _post(client, [
        _sched("sch_101", "18:00", "19:00", "팀플 회의"),
        _sched("sch_102", "20:00", "21:00", "저녁 약속"),
    ])
    data = body["data"]
    cands = data["recommended_candidates"]
    assert len(cands) == 1
    top = cands[0]
    assert top["candidate_id"] == "cand_001"
    assert top["start_time"] == "19:00"
    assert top["end_time"] == "20:00"
    assert top["conflict"] is False
    assert top["score"] >= 90          # base 80 + sandwich 10 (+ proximity)
    assert len(data["rejected_slots"]) == 2


# --------------------------------------------------------------------------- #
# 2. 기존 일정이 없으면 여러 후보, preferred_start 우선
# --------------------------------------------------------------------------- #
def test_case2_no_existing_returns_multiple_sorted(client):
    data = _post(client, [])["data"]
    cands = data["recommended_candidates"]
    assert len(cands) >= 2
    assert cands[0]["start_time"] == "18:00"          # closest to preferred_start
    assert all(c["conflict"] is False for c in cands)
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)     # highest score first
    assert data["rejected_slots"] == []


# --------------------------------------------------------------------------- #
# 3. 18:00~21:00 전부 차면 빈 배열 + 메시지
# --------------------------------------------------------------------------- #
def test_case3_full_window_returns_empty(client):
    body = _post(client, [_sched("x", "18:00", "21:00", "종일 워크숍")])
    assert body["success"] is True
    assert body["data"]["recommended_candidates"] == []
    assert body["message"] == "예약 가능한 시간이 없습니다."
    assert len(body["data"]["rejected_slots"]) == 1


# --------------------------------------------------------------------------- #
# 4. target_date와 다른 날짜의 일정은 무시
# --------------------------------------------------------------------------- #
def test_case4_other_date_schedules_ignored(client):
    body = _post(client, [
        _sched("other", "18:00", "21:00", "다른날 종일", date="2026-07-04"),
    ])
    data = body["data"]
    assert len(data["recommended_candidates"]) >= 1   # treated as no busy time
    assert data["rejected_slots"] == []


# --------------------------------------------------------------------------- #
# 5. duration_minutes가 90분 -> 가능한 구간만 반환
# --------------------------------------------------------------------------- #
def test_case5_duration_90_no_fitting_gap_is_empty(client):
    # only free gap is 19:00~20:00 (60 min) -> cannot fit 90 min
    body = _post(client, [
        _sched("a", "18:00", "19:00"),
        _sched("b", "20:00", "21:00"),
    ], duration_minutes=90)
    assert body["data"]["recommended_candidates"] == []
    assert body["message"] == "예약 가능한 시간이 없습니다."


def test_duration_90_returns_only_90min_slots(client):
    data = _post(client, [], duration_minutes=90)["data"]
    cands = data["recommended_candidates"]
    assert len(cands) >= 1
    for c in cands:
        sh, sm = map(int, c["start_time"].split(":"))
        eh, em = map(int, c["end_time"].split(":"))
        assert (eh * 60 + em) - (sh * 60 + sm) == 90
        assert eh * 60 + em <= 21 * 60                 # within preferred window


# --------------------------------------------------------------------------- #
# 10. 잘못된 시간 범위 -> 서버 에러 없이 빈 후보
# --------------------------------------------------------------------------- #
def test_invalid_time_range_is_safe(client):
    body = _post(client, [], preferred_start_time="21:00", preferred_end_time="18:00")
    assert body["success"] is True
    assert body["data"]["recommended_candidates"] == []


def test_malformed_time_is_safe(client):
    body = _post(client, [], preferred_start_time="2500", preferred_end_time="21:00")
    assert body["success"] is True
    assert body["data"]["recommended_candidates"] == []


# --------------------------------------------------------------------------- #
# Scoring: starts at/after 21:00 are penalized
# --------------------------------------------------------------------------- #
def test_late_start_is_penalized(client):
    data = _post(client, [], preferred_start_time="19:00", preferred_end_time="23:00")["data"]
    by_start = {c["start_time"]: c["score"] for c in data["recommended_candidates"]}
    assert "21:00" in by_start
    # a 21:00 start carries the -5 late penalty vs the 19:00 (preferred-start) slot
    assert by_start["21:00"] < by_start["19:00"]


# --------------------------------------------------------------------------- #
# Overlapping busy schedules: sandwich bonus must use MERGED boundaries
# --------------------------------------------------------------------------- #
def test_overlapping_busy_sandwich_uses_merged_edges(client):
    # busy 09:00-10:00 + 09:30-10:30 merge to 09:00-10:30; with 12:00-13:00 the
    # only free slot is 10:30-12:00 (90 min). A 90-min candidate fills it exactly
    # and must be sandwiched based on the MERGED edges 10:30 / 12:00.
    body = _post(client, [
        _sched("a", "09:00", "10:00", "수업"),
        _sched("b", "09:30", "10:30", "보강"),
        _sched("c", "12:00", "13:00", "점심"),
    ], target_date=DATE, preferred_start_time="09:00",
       preferred_end_time="13:00", duration_minutes=90)
    cands = body["data"]["recommended_candidates"]
    assert len(cands) == 1
    top = cands[0]
    assert top["start_time"] == "10:30" and top["end_time"] == "12:00"
    assert top["score"] >= 90              # base + sandwich(+10) applied
    assert "사이에" in top["reason"]
    assert len(body["data"]["rejected_slots"]) == 3


def test_overlapping_busy_partial_fill_has_no_false_sandwich(client):
    # Same merged free slot (10:30-12:00) but 60-min candidates do NOT fill it
    # exactly, so none should get the +10 sandwich bonus. The raw edges
    # 10:00 / 09:30 must not leak a bonus.
    body = _post(client, [
        _sched("a", "09:00", "10:00"),
        _sched("b", "09:30", "10:30"),
        _sched("c", "12:00", "13:00"),
    ], target_date=DATE, preferred_start_time="09:00",
       preferred_end_time="13:00", duration_minutes=60)
    cands = body["data"]["recommended_candidates"]
    assert len(cands) >= 1
    # no candidate fills 10:30-12:00 exactly -> no sandwich bonus -> score < 90
    assert all(c["score"] < 90 for c in cands)
    assert all(c["conflict"] is False for c in cands)
