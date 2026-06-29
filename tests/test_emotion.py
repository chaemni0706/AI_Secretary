"""Emotion analysis + life-coaching tests.

POST /api/v1/emotion/analyze

This is a life-coaching aid, NOT a medical diagnosis. Coaching must stay
suggestive ("보입니다", "추천합니다") and never use diagnostic wording.
Response fields are a frontend contract: sentiment / emotion / emotion_score /
risk_level / coaching / recommended_actions.
"""

PATH = "/api/v1/emotion/analyze"

# diagnostic phrasings that must never appear in coaching output
FORBIDDEN = ["우울증", "질환", "장애", "진단", "치료가 필요", "처방", "증상"]


def _post(client, text, **ctx):
    r = client.post(PATH, json={"input": text, "recent_context": ctx})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    return body["data"]


def _assert_non_diagnostic(coaching):
    for term in FORBIDDEN:
        assert term not in coaching, term


# --------------------------------------------------------------------------- #
# Response contract
# --------------------------------------------------------------------------- #
def test_response_structure_is_stable(client):
    data = _post(client, "오늘 너무 피곤해")
    assert set(data.keys()) == {
        "sentiment", "emotion", "emotion_score", "risk_level",
        "coaching", "recommended_actions",
    }
    assert 0.0 <= data["emotion_score"] <= 1.0
    assert data["risk_level"] in ("low", "medium", "high")


# --------------------------------------------------------------------------- #
# 1. fatigue (+ context reflected in actions)
# --------------------------------------------------------------------------- #
def test_case1_fatigue(client):
    data = _post(client, "오늘 너무 피곤하고 아무것도 하기 싫어",
                 sleep_hours=4.5, schedule_count=5, todo_done_rate=30)
    assert data["emotion"] == "fatigue"
    assert data["sentiment"] == "negative"
    assert data["emotion_score"] > 0.5
    # sleep < 6 and schedule_count >= 4 reflected
    assert "수면 시간 확보하기" in data["recommended_actions"]
    assert "저녁 일정 줄이기" in data["recommended_actions"]
    _assert_non_diagnostic(data["coaching"])


# --------------------------------------------------------------------------- #
# 2. anxiety
# --------------------------------------------------------------------------- #
def test_case2_anxiety(client):
    data = _post(client, "내일 발표 때문에 너무 불안해")
    assert data["emotion"] == "anxiety"
    assert data["sentiment"] == "negative"
    assert "할 일 잘게 쪼개기" in data["recommended_actions"]


# --------------------------------------------------------------------------- #
# 3. stress
# --------------------------------------------------------------------------- #
def test_case3_stress(client):
    data = _post(client, "일이 너무 많아서 스트레스 받아")
    assert data["emotion"] == "stress"
    assert {"우선순위 정리하기", "일정 재조정하기"}.issubset(set(data["recommended_actions"]))


# --------------------------------------------------------------------------- #
# 4. positive
# --------------------------------------------------------------------------- #
def test_case4_positive(client):
    data = _post(client, "오늘은 기분이 좋아")
    assert data["emotion"] == "positive"
    assert data["sentiment"] == "positive"
    assert "현재 루틴 유지하기" in data["recommended_actions"]


# --------------------------------------------------------------------------- #
# 5. neutral
# --------------------------------------------------------------------------- #
def test_case5_neutral(client):
    data = _post(client, "그냥 평범한 하루였어")
    assert data["emotion"] == "neutral"
    assert data["sentiment"] == "neutral"
    assert "하루 기록 유지하기" in data["recommended_actions"]
    assert data["coaching"]


# --------------------------------------------------------------------------- #
# Non-diagnostic, suggestive wording
# --------------------------------------------------------------------------- #
def test_non_diagnostic_wording(client):
    data = _post(client, "너무 우울하고 슬퍼")
    assert "보입니다" in data["coaching"]
    assert "추천" in data["coaching"]
    _assert_non_diagnostic(data["coaching"])


# --------------------------------------------------------------------------- #
# risk_level stays conservative (low/medium) for ordinary negative emotions
# --------------------------------------------------------------------------- #
def test_risk_level_conservative(client):
    sad = _post(client, "너무 우울하고 슬퍼")          # intensifier -> medium
    assert sad["risk_level"] in ("low", "medium")
    fatigue = _post(client, "조금 피곤하다")
    assert fatigue["risk_level"] in ("low", "medium")


def test_anger_actions(client):
    data = _post(client, "화가 나고 짜증나")
    assert data["emotion"] == "anger"
    assert {"잠시 멈추기", "천천히 호흡하기"}.issubset(set(data["recommended_actions"]))


# --------------------------------------------------------------------------- #
# Crisis safety: fixed safe message, high risk, suggests professional help
# --------------------------------------------------------------------------- #
def test_crisis_is_handled_safely(client):
    data = _post(client, "다 사라지고 싶어")
    assert data["risk_level"] == "high"
    assert "전문가" in data["coaching"]
    _assert_non_diagnostic(data["coaching"])
