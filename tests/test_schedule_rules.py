"""JSON rule-base engine tests (2차): category/title/location/participant rules
loaded from backend/rules/schedule_*.json and consumed by build_schedule_plan.
"""

from backend.services import schedule_rule_loader as rules
from backend.services.schedule_parser import build_schedule_plan

NOW = "2026-06-29T10:00:00+09:00"  # Monday


def _plan(text: str) -> dict:
    return build_schedule_plan(text, NOW)


# --------------------------------------------------------------------------- #
# rule files load correctly
# --------------------------------------------------------------------------- #
def test_rule_files_load():
    cats = rules.load_categories()
    expected = {
        "health", "beauty", "meal", "meeting", "study", "todo", "exercise",
        "reservation", "transport", "personal", "home", "finance", "shopping",
        "unknown",
    }
    assert expected.issubset(set(cats.keys()))
    # every category exposes the documented fields
    for spec in cats.values():
        assert "keywords" in spec and "title_rules" in spec
        assert "location_required" in spec

    sw = rules.load_stopwords()
    for group in ("first_person", "schedule_command_phrases", "intention_phrases",
                  "date_words", "time_words", "postpositions"):
        assert group in sw and isinstance(sw[group], list)

    pats = rules.load_patterns()
    assert pats["create_schedule_patterns"]
    assert pats["location_patterns"]
    assert pats["participant_patterns"]

    policy = rules.load_location_policy()
    assert "health" in policy["location_required_categories"]
    assert "온라인" in policy["online_keywords"]

    q = rules.load_clarification_questions()
    assert q["default"]["title"]
    assert q["health"]["location"]


def test_compiled_patterns_are_valid():
    cp = rules.compiled_patterns()
    assert any("title" in rx.groupindex for _, rx, _ in cp["create_schedule_patterns"])
    assert any("location" in rx.groupindex for _, rx, _ in cp["location_patterns"])


# --------------------------------------------------------------------------- #
# spec §9 acceptance cases
# --------------------------------------------------------------------------- #
def test_case_hospital_intent():
    p = _plan("나 병원 가려고 일정 잡아줘")
    assert p["category"] == "health"
    assert p["title"] == "병원 방문"
    assert {"date", "time", "location"}.issubset(set(p["missing_fields"]))


def test_case_hospital_specific_place_complete():
    p = _plan("내일 오후 3시에 포항성모병원 가려고 일정 잡아줘")
    assert p["category"] == "health"
    assert p["location"] == "포항성모병원"
    assert p["missing_fields"] == []


def test_case_beauty():
    p = _plan("미용실 예약 잡아줘")
    assert p["category"] == "beauty"
    assert p["title"] == "미용실 예약"
    assert {"date", "time", "location"}.issubset(set(p["missing_fields"]))


def test_case_meeting_consultation():
    p = _plan("교수님 상담 일정 잡아줘")
    assert p["category"] == "meeting"
    assert p["title"] in ("교수님 상담", "상담")
    assert "date" in p["missing_fields"] and "time" in p["missing_fields"]
    assert "location" not in p["missing_fields"]


def test_case_todo():
    p = _plan("과제 해야 해")
    assert p["category"] == "todo"
    assert p["title"] == "과제"
    assert "location" not in p["missing_fields"]
    assert "date" in p["missing_fields"]


def test_case_meal_with_person():
    p = _plan("민수랑 카페 가는 거 추가해줘")
    assert p["category"] == "meal"
    assert p["title"] in ("민수랑 카페", "민수와 카페")
    assert "민수" in p["participants"]
    assert "location" in p["missing_fields"]


def test_case_online_meeting_no_location():
    p = _plan("온라인 회의 일정 잡아줘")
    assert p["category"] == "meeting"
    assert "location" not in p["missing_fields"]


def test_case_gym_exercise():
    p = _plan("헬스장 운동 등록해줘")
    assert p["category"] == "exercise"
    assert p["title"] == "헬스장 운동"
    # exercise is optional but a place keyword (헬스장) makes location required
    assert "location" in p["missing_fields"]


def test_case_finance():
    p = _plan("카드값 납부해야 해")
    assert p["category"] == "finance"
    assert p["title"] == "카드값 납부"


def test_case_family_dinner():
    p = _plan("내일 저녁 가족들이랑 밥 약속 잡아줘")
    assert p["category"] == "meal"
    assert p["title"] in ("가족들과 저녁 약속", "식사 약속")
    assert "time" in p["missing_fields"]
    assert "location" in p["missing_fields"]
