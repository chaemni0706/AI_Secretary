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


# --------------------------------------------------------------------------- #
# Stage 3 — checklist coverage / leave-time / robustness / sort
# (case1 병원+비, case3 exercise+hot dedup are already locked above.)
# --------------------------------------------------------------------------- #
def test_meeting_checklist(client):
    items = _items(_post(client, category="meeting", title="팀 회의")["data"])
    assert {"노트북", "회의자료", "충전기"}.issubset(set(items))


def test_school_checklist(client):
    items = _items(_post(client, category="school", title="오전 수업")["data"])
    assert {"노트북", "교재", "필기구"}.issubset(set(items))


def test_exercise_checklist_full(client):
    items = _items(_post(client, category="exercise", title="헬스")["data"])
    assert {"운동복", "물", "수건"}.issubset(set(items))


def test_snow_and_cold_weather_items(client):
    snow = _items(_post(client, category="etc", weather="snow")["data"])
    assert "외투" in snow and "장갑" in snow            # 따뜻한 옷 계열
    cold = _items(_post(client, category="etc", weather="cold")["data"])
    assert "외투" in cold and "장갑" in cold


def test_leave_time_calculation_14_to_1320(client):
    data = _post(client, start="14:00", travel=30, buffer=10)["data"]
    assert data["leave_time"] == "13:20"               # 14:00 - 30 - 10


def _post_ctx(client, ctx):
    r = client.post(PATH, json={
        "schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00"},
        "context": ctx, "user_preference": {},
    })
    assert r.status_code == 200
    return r.json()["data"]


def test_travel_minutes_default_used_when_omitted(client):
    data = _post_ctx(client, {"buffer_minutes": 10})    # travel default 0
    assert data["leave_time"] == "13:50"               # 14:00 - 0 - 10


def test_buffer_minutes_default_used_when_omitted(client):
    data = _post_ctx(client, {"estimated_travel_minutes": 30})  # buffer default 0
    assert data["leave_time"] == "13:30"               # 14:00 - 30 - 0


def test_huge_travel_minutes_is_safe(client):
    data = _post(client, start="14:00", travel=5000, buffer=0)["data"]
    assert data["leave_time"] == "00:00"               # clamped, no error
    assert len(data["notifications"]) >= 1
    assert all(n["message"] for n in data["notifications"])   # no empty messages


def test_checklist_has_no_duplicate_items(client):
    items = _items(_post(client, category="exercise", weather="hot")["data"])
    assert len(items) == len(set(items))               # 물(base) + 물(hot) -> 1


def test_notifications_are_time_sorted(client):
    for style, forgetful in (("strong", True), ("normal", False)):
        data = _post(client, style=style, forgetful=forgetful,
                     start="14:00", travel=35, buffer=10)["data"]
        times = [n["time"] for n in data["notifications"]]
        assert times == sorted(times)


# --------------------------------------------------------------------------- #
# Stage 3-1 — late_prone preference (A-plan: optional, additive, default False)
# --------------------------------------------------------------------------- #
def _post_pref(client, pref):
    r = client.post(PATH, json={
        "schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00"},
        "context": {"estimated_travel_minutes": 35, "buffer_minutes": 10},
        "user_preference": pref,
    })
    assert r.status_code == 200
    return r.json()["data"]


def test_late_prone_adds_pre_departure_reminder(client):
    base = _post_pref(client, {"notification_style": "normal"})
    late = _post_pref(client, {"notification_style": "normal", "late_prone": True})
    base_times = [n["time"] for n in base["notifications"]]
    late_times = [n["time"] for n in late["notifications"]]
    assert base_times == ["13:15", "13:30"]            # no extra without late_prone
    assert "13:05" in late_times                       # leave(13:15) - 10
    assert late_times == sorted(late_times)


def test_late_prone_default_false_is_backward_compatible(client):
    # omitting late_prone behaves exactly like before
    omitted = _post_pref(client, {"notification_style": "normal"})
    explicit_false = _post_pref(client, {"notification_style": "normal", "late_prone": False})
    assert [n["time"] for n in omitted["notifications"]] == \
           [n["time"] for n in explicit_false["notifications"]]


# --------------------------------------------------------------------------- #
# Stage 3-2 — late_prone fully separated from forgetful
# --------------------------------------------------------------------------- #
def _times_leq(notifs, hhmm):
    limit = int(hhmm[:2]) * 60 + int(hhmm[3:])
    return [n["time"] for n in notifs
            if int(n["time"][:2]) * 60 + int(n["time"][3:]) <= limit]


def test_late_prone_passes_schema_validation(client):
    data = _post_pref(client, {"notification_style": "normal", "late_prone": True})
    assert data["leave_time"] == "13:15"               # request accepted, computed
    assert data["notifications"]


def test_late_prone_has_more_and_earlier_departure_reminders(client):
    normal = _post_pref(client, {"notification_style": "normal"})["notifications"]
    late = _post_pref(client, {"notification_style": "normal", "late_prone": True})["notifications"]
    # more reminders at/before the leave time
    assert len(_times_leq(late, "13:15")) > len(_times_leq(normal, "13:15"))
    # and an earlier first reminder
    assert min(n["time"] for n in late) < min(n["time"] for n in normal)
    assert [n["time"] for n in late] == sorted(n["time"] for n in late)


def test_forgetful_and_late_prone_are_distinct(client):
    forgetful = [n["time"] for n in
                 _post_pref(client, {"notification_style": "normal", "forgetful": True})["notifications"]]
    late = [n["time"] for n in
            _post_pref(client, {"notification_style": "normal", "late_prone": True})["notifications"]]
    assert forgetful != late
    assert "13:00" in forgetful and "13:00" not in late   # forgetful: extra pre-start (60m)
    assert "12:55" in late and "12:55" not in forgetful   # late_prone: earlier departure (20m)
