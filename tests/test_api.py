"""Cross-API contract tests.

Backend quality gate that runs without any frontend: every endpoint must
return status 200 with the common {success, message, data} envelope and its
documented core fields. Plus key edge scenarios.
"""

V1 = "/api/v1"

# Local constants (do NOT import from conftest — that breaks under
# --import-mode=importlib). NOW is a Monday so relative dates resolve
# deterministically.
NOW = "2026-06-29T10:00:00+09:00"
MD = "2026-06-30"

# Valid, minimal-but-complete payloads for each POST endpoint.
SCHEDULE = (f"{V1}/ai/schedule/parse",
            {"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": NOW})
RESERVATION = (f"{V1}/reservations/candidates", {
    "constraints": {"target_date": "2026-07-03", "preferred_start_time": "18:00",
                    "preferred_end_time": "21:00", "duration_minutes": 60},
    "existing_schedules": [],
})
MESSAGE = (f"{V1}/messages/reservation", {
    "reservation_info": {"category": "hospital", "target_date": MD,
                         "preferred_time": "10:00", "purpose": "진료 예약"},
})
ALERT = (f"{V1}/alerts/departure-plan", {
    "schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00"},
    "context": {"weather": "rain", "estimated_travel_minutes": 35, "buffer_minutes": 10},
})
BRIEFING = (f"{V1}/briefings/daily", {
    "date": MD,
    "schedules": [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}],
    "todos": [{"title": "진료카드 챙기기", "priority": "high", "is_done": False}],
})
EMOTION = (f"{V1}/emotion/analyze",
           {"input": "오늘 너무 피곤해", "recent_context": {}})

ALL_POSTS = [SCHEDULE, RESERVATION, MESSAGE, ALERT, BRIEFING, EMOTION]


# --------------------------------------------------------------------------- #
# Common envelope across every endpoint
# --------------------------------------------------------------------------- #
def test_health(client, check_envelope):
    r = client.get("/health")
    assert r.status_code == 200
    data = check_envelope(r.json())
    assert data["status"] == "ok"


def test_unknown_route_returns_common_error(client, check_envelope):
    r = client.get(f"{V1}/does-not-exist")
    assert r.status_code == 404
    check_envelope(r.json(), success=False)


def test_all_post_endpoints_return_envelope_with_data(post):
    for path, payload in ALL_POSTS:
        body = post(path, payload)
        assert body["data"] is not None, path


# --------------------------------------------------------------------------- #
# Per-API required core fields
# --------------------------------------------------------------------------- #
def test_schedule_required_fields(post):
    data = post(*SCHEDULE)["data"]
    assert "schedule_draft" in data and "slots" in data
    draft = data["schedule_draft"]
    for f in ("title", "date", "start_time", "category"):
        assert f in draft, f
    assert isinstance(data["missing_fields"], list)


def test_reservation_required_fields(post):
    data = post(*RESERVATION)["data"]
    assert "recommended_candidates" in data and "rejected_slots" in data
    assert isinstance(data["recommended_candidates"], list)
    assert isinstance(data["rejected_slots"], list)
    for cand in data["recommended_candidates"]:        # when candidates exist
        for f in ("start_time", "end_time", "score", "candidate_id", "conflict"):
            assert f in cand, f


def test_message_required_fields(post):
    data = post(*MESSAGE)["data"]
    assert data["generated_message"]
    assert isinstance(data["alternatives"], list) and len(data["alternatives"]) >= 2


def test_alert_required_fields(post):
    data = post(*ALERT)["data"]
    assert data["leave_time"]                          # valid start_time -> present
    assert isinstance(data["checklist"], list) and data["checklist"]
    assert isinstance(data["notifications"], list)


def test_briefing_required_fields(post):
    data = post(*BRIEFING)["data"]
    assert data["summary"]
    assert isinstance(data["key_points"], list)
    assert isinstance(data["priority_order"], list) and data["priority_order"]


def test_emotion_required_fields(post):
    data = post(*EMOTION)["data"]
    assert data["emotion"]
    assert data["coaching"]
    assert data["sentiment"] in ("positive", "neutral", "negative")


# --------------------------------------------------------------------------- #
# Additional edge scenarios
# --------------------------------------------------------------------------- #
def test_schedule_without_date_or_time(post):
    data = post(f"{V1}/ai/schedule/parse",
                {"input": "병원 예약 잡아줘", "current_datetime": NOW})["data"]
    assert "date" in data["missing_fields"]
    assert "time" in data["missing_fields"]
    assert data["slots"]["date"] is None
    assert data["slots"]["start_time"] is None


def test_reservation_no_available_slot(post):
    body = post(f"{V1}/reservations/candidates", {
        "constraints": {"target_date": "2026-07-03", "preferred_start_time": "18:00",
                        "preferred_end_time": "21:00", "duration_minutes": 60},
        "existing_schedules": [
            {"id": "x", "title": "종일", "date": "2026-07-03",
             "start_time": "18:00", "end_time": "21:00"},
        ],
    })
    assert body["data"]["recommended_candidates"] == []
    assert body["message"] == "예약 가능한 시간이 없습니다."


def test_alert_rain_includes_umbrella(post):
    data = post(f"{V1}/alerts/departure-plan", {
        "schedule": {"title": "외출", "category": "etc", "start_time": "14:00"},
        "context": {"weather": "rain", "estimated_travel_minutes": 20, "buffer_minutes": 5},
    })["data"]
    assert "우산" in [c["item"] for c in data["checklist"]]


def test_emotion_neutral_when_no_keyword(post):
    data = post(f"{V1}/emotion/analyze",
                {"input": "그냥 평범한 하루였어", "recent_context": {}})["data"]
    assert data["emotion"] == "neutral"
    assert data["coaching"]


def test_briefing_with_no_schedules(post):
    data = post(f"{V1}/briefings/daily",
                {"date": MD, "schedules": [], "todos": []})["data"]
    assert data["summary"]
    assert data["priority_order"] == []
