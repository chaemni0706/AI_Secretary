def test_emotion_fatigue(client):
    r = client.post("/api/v1/emotion/analyze", json={
        "input": "오늘 너무 피곤하고 아무것도 하기 싫어", "date": "2026-06-30",
        "recent_context": {"sleep_hours": 4.5, "schedule_count": 5, "todo_done_rate": 30},
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["emotion"] == "fatigue"
    assert data["sentiment"] == "negative"
    assert data["coaching"]
    assert len(data["recommended_actions"]) >= 1


def test_emotion_neutral(client):
    r = client.post("/api/v1/emotion/analyze", json={"input": "오늘 점심으로 김밥을 먹었다", "recent_context": {}})
    data = r.json()["data"]
    assert data["emotion"] == "neutral"
    assert data["coaching"]


def test_emotion_non_diagnostic_wording(client):
    r = client.post("/api/v1/emotion/analyze", json={"input": "너무 우울하고 슬퍼", "recent_context": {}})
    data = r.json()["data"]
    # 비진단 표현 확인
    assert "보입니다" in data["coaching"]
    assert "추천" in data["coaching"]
