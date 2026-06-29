"""Schedule parsing tests (POST /api/v1/ai/schedule/parse).

Covers the 8 sample utterances plus edge cases for date / time / title /
category / priority and missing-field handling. The response envelope and
field names must stay stable for the Flutter frontend.

current_datetime is fixed to a Monday (2026-06-29) so relative date
expressions resolve deterministically.
"""

NOW = "2026-06-29T10:00:00+09:00"  # Monday
PATH = "/api/v1/ai/schedule/parse"


def _parse(client, text):
    r = client.post(PATH, json={"input": text, "current_datetime": NOW})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["message"] == "일정 정보를 추출했습니다."
    assert body["data"] is not None
    return body["data"]


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert set(data.keys()) == {
        "intent", "confidence", "slots", "schedule_draft", "missing_fields"
    }
    assert set(data["slots"].keys()) == {
        "title", "date_expression", "time_expression", "date",
        "start_time", "end_time", "category", "location",
    }
    assert set(data["schedule_draft"].keys()) == {
        "title", "category", "date", "start_time", "end_time",
        "location", "memo", "priority", "source",
    }
    assert data["schedule_draft"]["source"] == "ai"
    assert data["slots"]["location"] is None


# 1. 내일 오후 2시에 병원 예약 잡아줘
def test_case1_tomorrow_afternoon_hospital(client):
    data = _parse(client, "내일 오후 2시에 병원 예약 잡아줘")
    assert data["intent"] == "create_schedule"
    assert data["confidence"] == 0.94
    assert data["slots"]["date"] == "2026-06-30"
    assert data["slots"]["start_time"] == "14:00"
    assert data["slots"]["end_time"] == "15:00"
    assert data["slots"]["category"] == "hospital"
    assert data["schedule_draft"]["priority"] == "high"
    assert data["missing_fields"] == []


# 2. 다음 주 월요일 오전 10시에 팀 회의 추가해줘
def test_case2_next_monday_morning_meeting(client):
    data = _parse(client, "다음 주 월요일 오전 10시에 팀 회의 추가해줘")
    assert data["intent"] == "create_schedule"
    assert data["slots"]["date"] == "2026-07-06"   # next Monday
    assert data["slots"]["start_time"] == "10:00"
    assert data["slots"]["category"] == "meeting"
    assert data["schedule_draft"]["priority"] == "high"
    assert "회의" in data["slots"]["title"]
    assert data["missing_fields"] == []


# 3. 금요일 저녁 7시에 친구랑 약속 있어
def test_case3_weekday_evening_personal(client):
    data = _parse(client, "금요일 저녁 7시에 친구랑 약속 있어")
    assert data["slots"]["date"] == "2026-07-03"   # this week's Friday
    assert data["slots"]["start_time"] == "19:00"
    assert data["slots"]["category"] == "personal"
    assert data["schedule_draft"]["priority"] == "medium"
    assert data["missing_fields"] == []


# 4. 오늘 밤 11시에 과제 마감 알림해줘
def test_case4_today_night_study_deadline(client):
    data = _parse(client, "오늘 밤 11시에 과제 마감 알림해줘")
    assert data["slots"]["date"] == "2026-06-29"   # today
    assert data["slots"]["start_time"] == "23:00"
    assert data["slots"]["category"] == "study"
    assert data["schedule_draft"]["priority"] == "high"   # '마감' keyword
    assert data["missing_fields"] == []


# 5. 7월 3일 3시에 미용실 예약 넣어줘  (ambiguous time -> 15:00)
def test_case5_month_day_ambiguous_time_beauty(client):
    data = _parse(client, "7월 3일 3시에 미용실 예약 넣어줘")
    assert data["slots"]["date"] == "2026-07-03"
    assert data["slots"]["start_time"] == "15:00"   # afternoon default
    assert data["slots"]["category"] == "beauty"
    assert data["schedule_draft"]["priority"] == "medium"
    assert "time_ambiguity" in data["missing_fields"]
    assert "time" not in data["missing_fields"]      # time WAS estimated


# 6. 모레 아침 8시에 운동 일정 추가해줘
def test_case6_day_after_tomorrow_morning_exercise(client):
    data = _parse(client, "모레 아침 8시에 운동 일정 추가해줘")
    assert data["slots"]["date"] == "2026-07-01"
    assert data["slots"]["start_time"] == "08:00"
    assert data["slots"]["category"] == "exercise"
    assert data["schedule_draft"]["priority"] == "medium"
    assert data["missing_fields"] == []


# 7. 병원 예약 잡아줘  (no date / no time)
def test_case7_no_date_no_time_reports_missing(client):
    data = _parse(client, "병원 예약 잡아줘")
    assert data["intent"] == "create_schedule"       # title+category present
    assert data["slots"]["category"] == "hospital"
    assert data["schedule_draft"]["priority"] == "high"
    assert "date" in data["missing_fields"]
    assert "time" in data["missing_fields"]
    assert data["slots"]["date"] is None
    assert data["slots"]["start_time"] is None


# 8. 내일 약속 잡아줘  (date only, no time)
def test_case8_tomorrow_no_time(client):
    data = _parse(client, "내일 약속 잡아줘")
    assert data["slots"]["date"] == "2026-06-30"
    assert data["slots"]["category"] == "personal"
    assert "time" in data["missing_fields"]
    assert "date" not in data["missing_fields"]


# Time-of-day mapping
def test_time_meridiem_mapping(client):
    cases = {
        "내일 오전 10시에 회의": "10:00",
        "내일 오후 2시에 회의": "14:00",
        "내일 저녁 7시에 회의": "19:00",
        "내일 밤 11시에 회의": "23:00",
        "내일 아침 8시에 회의": "08:00",
    }
    for text, expected in cases.items():
        data = _parse(client, text)
        assert data["slots"]["start_time"] == expected, text


# Edge cases
def test_empty_input_is_safe(client):
    data = _parse(client, "")
    assert "date" in data["missing_fields"]
    assert "time" in data["missing_fields"]
    assert "title" in data["missing_fields"]
    assert data["intent"] == "unknown"


def test_this_week_friday(client):
    data = _parse(client, "이번 주 금요일 오후 3시에 회의 잡아줘")
    assert data["slots"]["date"] == "2026-07-03"
    assert data["slots"]["start_time"] == "15:00"
    assert "time_ambiguity" not in data["missing_fields"]


# --------------------------------------------------------------------------- #
# Time-parsing robustness regression tests
# --------------------------------------------------------------------------- #
def test_invalid_minute_is_not_parsed(client):
    # "2시 70분" must NOT become "14:70"; minute out of range -> no valid time.
    data = _parse(client, "오늘 2시 70분 회의")
    assert data["slots"]["start_time"] != "14:70"
    assert data["slots"]["start_time"] is None
    assert "time" in data["missing_fields"]


def test_invalid_hour_is_not_normalized(client):
    # "25시" must NOT be silently wrapped to "01:00"; hour out of range -> none.
    data = _parse(client, "내일 25시 병원 예약")
    assert data["slots"]["start_time"] != "01:00"
    assert data["slots"]["start_time"] is None
    assert "time" in data["missing_fields"]
    # the rest of the parse still works
    assert data["slots"]["date"] == "2026-06-30"
    assert data["slots"]["category"] == "hospital"


def test_duration_is_not_parsed_as_clock_time(client):
    # "3시간" (duration) must NOT be read as "3시" -> 15:00/03:00.
    data = _parse(client, "3시간 회의 잡아줘")
    assert data["slots"]["start_time"] not in ("15:00", "03:00")
    assert data["slots"]["start_time"] is None
    assert "time" in data["missing_fields"]
    # still recognized as a (time-less) meeting schedule
    assert data["slots"]["category"] == "meeting"


def test_bare_three_oclock_still_parses(client):
    # "3시" without 오전/오후 keeps the afternoon-default policy (15:00).
    data = _parse(client, "오늘 3시 회의")
    assert data["slots"]["start_time"] == "15:00"
    assert "time_ambiguity" in data["missing_fields"]


# --------------------------------------------------------------------------- #
# Duration expressions must be stripped from the title (not parsed as time)
# --------------------------------------------------------------------------- #
def test_duration_hours_stripped_from_title(client):
    data = _parse(client, "3시간 회의 잡아줘")
    assert data["slots"]["title"] == "회의"
    assert data["schedule_draft"]["title"] == "회의"
    assert data["slots"]["start_time"] is None   # duration is not a clock time


def test_duration_hours_minutes_stripped_from_title(client):
    data = _parse(client, "1시간 30분 회의 잡아줘")
    assert data["slots"]["title"] == "회의"
    assert data["slots"]["start_time"] is None


def test_duration_minutes_stripped_from_title(client):
    data = _parse(client, "30분 산책 일정 추가해줘")
    assert data["slots"]["title"] == "산책"
    assert data["slots"]["start_time"] is None


def test_real_time_kept_while_title_clean(client):
    # A real clock time is still parsed; the title stays clean.
    data = _parse(client, "오늘 3시 회의 잡아줘")
    assert data["slots"]["title"] == "회의"
    assert data["slots"]["start_time"] == "15:00"
    assert "time_ambiguity" in data["missing_fields"]


# --------------------------------------------------------------------------- #
# Duration trailing suffixes (만/짜리/동안) must also be stripped from the title
# --------------------------------------------------------------------------- #
def test_duration_suffix_man_stripped(client):
    data = _parse(client, "30분만 산책 일정 추가해줘")
    assert data["slots"]["title"] == "산책"
    assert data["slots"]["start_time"] is None


def test_duration_suffix_jjari_stripped(client):
    data = _parse(client, "2시간 30분짜리 회의 잡아줘")
    assert data["slots"]["title"] == "회의"
    assert data["slots"]["start_time"] is None


def test_duration_suffix_dongan_stripped(client):
    data = _parse(client, "1시간 동안 운동 일정 추가해줘")
    assert data["slots"]["title"] == "운동"
    assert data["slots"]["start_time"] is None


def test_duration_suffix_does_not_eat_words(client):
    # "만" guard: "만남" must not be truncated to "남".
    data = _parse(client, "30분 만남 추가해줘")
    assert data["slots"]["title"] == "만남"
    assert data["slots"]["category"] == "personal"
