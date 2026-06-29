def test_daily_briefing(client):
    r = client.post("/api/v1/briefings/daily", json={
        "date": "2026-06-30",
        "schedules": [
            {"title": "오전 수업", "category": "school", "start_time": "09:00", "end_time": "12:00", "priority": "medium"},
            {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "end_time": "15:00", "priority": "high"},
            {"title": "팀플 회의", "category": "meeting", "start_time": "19:00", "end_time": "20:00", "priority": "high"},
        ],
        "todos": [{"title": "진료카드 챙기기", "priority": "high", "is_done": False}],
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["summary"]
    assert len(data["key_points"]) >= 1
    assert len(data["priority_order"]) >= 1
    titles = [p["title"] for p in data["priority_order"]]
    assert "병원 예약" in titles


def test_empty_briefing(client):
    r = client.post("/api/v1/briefings/daily", json={"date": "2026-06-30", "schedules": [], "todos": []})
    assert r.status_code == 200
    assert r.json()["data"]["summary"]
