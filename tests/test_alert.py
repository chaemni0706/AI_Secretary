"""Departure / preparation alert tests.

POST /api/v1/alerts/departure-plan

Response field names are part of the frontend contract and must stay stable:
data.leave_time / estimated_travel_minutes / buffer_minutes / checklist /
notifications, plus checklist[].item/reason and notifications[].time/message.
"""

PATH = "/api/v1/alerts/departure-plan"


def _post(client, *, category="hospital", title="병원 예약", start="14:00",
          weather=None, travel=35, buffer=10, style="normal", forgetful=False):
    payload = {
        "schedule": {"title": title, "category": category, "start_time": start},
        "context": {"weather": weather, "estimated_travel_minutes": travel,
                    "buffer_minutes": buffer},
        "user_preference": {"notification_style": style, "forgetful": forgetful},
    }
    r = client.post(PATH, json=payload)
    assert r.status_code == 200
    return r.json()


def _items(data):
    return [c["item"] for c in data["checklist"]]


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    data = _post(client)["data"]
    assert set(data.keys()) == {
        "leave_time", "estimated_travel_minutes", "buffer_minutes",
        "checklist", "notifications",
    }
    assert set(data["checklist"][0].keys()) == {"item", "reason"}
    assert set(data["notifications"][0].keys()) == {"time", "message"}


# --------------------------------------------------------------------------- #
# 1. 병원 + rain + 이동 35 + buffer 10 -> leave 13:15, 우산 포함
# --------------------------------------------------------------------------- #
def test_case1_hospital_rain_leave_time_and_umbrella(client):
    data = _post(client, category="hospital", weather="rain",
                 travel=35, buffer=10, start="14:00")["data"]
    assert data["leave_time"] == "13:15"            # 14:00 - 35 - 10
    assert data["estimated_travel_minutes"] == 35
    assert data["buffer_minutes"] == 10
    items = _items(data)
    assert "우산" in items
    assert "신분증" in items                          # hospital base


# --------------------------------------------------------------------------- #
# 2. school + sunny -> 노트북, 교재, 필기구 (no weather extra)
# --------------------------------------------------------------------------- #
def test_case2_school_sunny_checklist(client):
    data = _post(client, category="school", weather="sunny")["data"]
    items = _items(data)
    assert {"노트북", "교재", "필기구"}.issubset(set(items))
    # sunny adds nothing
    assert len(items) == 3


# --------------------------------------------------------------------------- #
# 3. exercise + hot -> 물이 중복 없이 한 번만
# --------------------------------------------------------------------------- #
def test_case3_exercise_hot_dedupes_water(client):
    data = _post(client, category="exercise", weather="hot")["data"]
    items = _items(data)
    assert "물" in items
    assert items.count("물") == 1                     # base 물 + hot 물 -> 1
    assert "운동복" in items


# --------------------------------------------------------------------------- #
# 4. strong -> 알림 3개 이상
# --------------------------------------------------------------------------- #
def test_case4_strong_has_three_or_more_notifications(client):
    data = _post(client, style="strong", start="14:00", travel=35, buffer=10)["data"]
    times = [n["time"] for n in data["notifications"]]
    assert len(times) >= 3
    assert times == sorted(times)                     # naturally ordered
    assert "13:15" in times                           # leave-time reminder


# --------------------------------------------------------------------------- #
# 5. normal -> 알림 2개 정도
# --------------------------------------------------------------------------- #
def test_case5_normal_has_two_notifications(client):
    data = _post(client, style="normal", start="14:00", travel=35, buffer=10)["data"]
    times = [n["time"] for n in data["notifications"]]
    assert len(times) == 2
    assert times == sorted(times)
    assert "13:15" in times and "13:30" in times       # leave + 30-before-start


# --------------------------------------------------------------------------- #
# restaurant / study categories
# --------------------------------------------------------------------------- #
def test_restaurant_and_study_checklists(client):
    assert "예약 확인 문자" in _items(_post(client, category="restaurant")["data"])
    study_items = _items(_post(client, category="study")["data"])
    assert {"노트북", "교재", "필기구"}.issubset(set(study_items))


# --------------------------------------------------------------------------- #
# Forgetful = stronger style + extra leave-soon reminder
# --------------------------------------------------------------------------- #
def test_forgetful_escalates_and_adds_extra(client):
    data = _post(client, style="normal", forgetful=True,
                 start="14:00", travel=35, buffer=10)["data"]
    times = [n["time"] for n in data["notifications"]]
    # escalated to strong (60/30 before start) + leave + leave-10
    assert len(times) >= 4
    assert "13:05" in times                            # leave(13:15) - 10


# --------------------------------------------------------------------------- #
# Notification de-dup on identical times
# --------------------------------------------------------------------------- #
def test_notifications_dedupe_identical_times(client):
    # travel+buffer == 30 -> leave == start-30 -> the two times collide.
    data = _post(client, style="normal", start="14:00", travel=30, buffer=0)["data"]
    times = [n["time"] for n in data["notifications"]]
    assert len(times) == len(set(times))               # no duplicate times
    assert times == ["13:30"]


# --------------------------------------------------------------------------- #
# Robustness: malformed start time
# --------------------------------------------------------------------------- #
def test_invalid_start_time_is_safe(client):
    r = client.post(PATH, json={
        "schedule": {"title": "x", "category": "etc", "start_time": "25:99"},
        "context": {}, "user_preference": {},
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["leave_time"] is None
    assert data["notifications"] == []
    assert len(data["checklist"]) >= 1                 # checklist still built
