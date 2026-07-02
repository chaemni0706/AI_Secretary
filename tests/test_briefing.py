"""Daily briefing tests.

POST /api/v1/briefings/daily

Response field names are part of the frontend contract: data.summary /
data.key_points / data.priority_order (each item: title/priority/reason).
Summary is rule-based template text here (no LLM key in the test env).
"""

PATH = "/api/v1/briefings/daily"
DATE = "2026-06-30"


def _post(client, schedules, todos):
    r = client.post(PATH, json={"date": DATE, "schedules": schedules, "todos": todos})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    return body["data"]


def _po(data):
    return {p["title"]: p["priority"] for p in data["priority_order"]}


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    data = _post(client, [
        {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"},
    ], [])
    assert set(data.keys()) == {"summary", "key_points", "priority_order"}
    assert isinstance(data["summary"], str) and data["summary"]
    assert set(data["priority_order"][0].keys()) == {"title", "priority", "reason"}


# --------------------------------------------------------------------------- #
# 1. 오전 수업 + 오후 병원 + 저녁 회의
# --------------------------------------------------------------------------- #
def test_case1_morning_afternoon_evening(client):
    data = _post(client, [
        {"title": "오전 수업", "category": "school", "start_time": "09:00", "end_time": "12:00", "priority": "medium"},
        {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "end_time": "15:00", "priority": "high"},
        {"title": "팀플 회의", "category": "meeting", "start_time": "19:00", "end_time": "20:00", "priority": "high"},
    ], [{"title": "진료카드 챙기기", "priority": "high", "is_done": False}])

    # natural day-part phrasing
    assert "오전 수업" in data["summary"]
    assert "오후 병원 예약" in data["summary"]
    assert "저녁 팀플 회의" in data["summary"]
    assert "진료카드" in data["summary"]              # prep tip from high to-do

    po = _po(data)
    assert po["병원 예약"] == "high" and po["팀플 회의"] == "high"
    assert po["오전 수업"] == "medium"
    # priority_order includes ALL schedules, high first
    assert [p["title"] for p in data["priority_order"]] == ["병원 예약", "팀플 회의", "오전 수업"]
    # undone high to-do appears in key_points
    assert any("진료카드" in k for k in data["key_points"])


# --------------------------------------------------------------------------- #
# 2. 일정 없음 + To-do만
# --------------------------------------------------------------------------- #
def test_case2_no_schedules_only_todos(client):
    data = _post(client, [], [{"title": "과제 제출하기", "priority": "high", "is_done": False}])
    assert data["summary"]                            # natural fallback summary
    assert data["priority_order"] == []
    assert any("과제 제출하기" in k for k in data["key_points"])


# --------------------------------------------------------------------------- #
# 3. 일정과 To-do 모두 없음
# --------------------------------------------------------------------------- #
def test_case3_empty(client):
    data = _post(client, [], [])
    assert data["summary"]                            # still returns a briefing
    assert data["priority_order"] == []


# --------------------------------------------------------------------------- #
# 4. high priority 일정 여러 개 -> 중요도 순 정렬, high 먼저
# --------------------------------------------------------------------------- #
def test_case4_multiple_high_priority(client):
    data = _post(client, [
        {"title": "기말 시험", "category": "study", "start_time": "10:00", "priority": "medium"},
        {"title": "병원 예약", "category": "hospital", "start_time": "15:00", "priority": "medium"},
        {"title": "점심 약속", "category": "personal", "start_time": "12:00", "priority": "medium"},
    ], [])
    po = _po(data)
    assert po["기말 시험"] == "high"                   # '시험' keyword boost
    assert po["병원 예약"] == "high"                   # hospital + '예약' boost
    assert po["점심 약속"] == "medium"
    titles = [p["title"] for p in data["priority_order"]]
    # highs first (by time), medium last
    assert titles[:2] == ["기말 시험", "병원 예약"]
    assert titles[-1] == "점심 약속"


# --------------------------------------------------------------------------- #
# 5. 완료된 To-do는 강조하지 않음
# --------------------------------------------------------------------------- #
def test_case5_completed_todo_not_emphasized(client):
    data = _post(client, [
        {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"},
    ], [{"title": "진료카드 챙기기", "priority": "high", "is_done": True}])
    assert not any("진료카드" in k for k in data["key_points"])


# --------------------------------------------------------------------------- #
# priority_order keeps non-high schedules too (regression)
# --------------------------------------------------------------------------- #
def test_priority_order_includes_all_schedules(client):
    data = _post(client, [
        {"title": "오전 수업", "category": "school", "start_time": "09:00", "priority": "medium"},
        {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"},
    ], [])
    assert len(data["priority_order"]) == 2
    assert "오전 수업" in _po(data)
