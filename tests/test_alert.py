def test_departure_plan(client):
    r = client.post("/api/v1/alerts/departure-plan", json={
        "schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "location": "서울OO병원"},
        "context": {"weather": "rain", "estimated_travel_minutes": 35, "buffer_minutes": 10},
        "user_preference": {"notification_style": "strong", "forgetful": True},
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["leave_time"] == "13:15"
    assert len(data["checklist"]) >= 1
    items = [c["item"] for c in data["checklist"]]
    assert "우산" in items  # rain rule
    assert len(data["notifications"]) >= 1


def test_invalid_start_time_is_safe(client):
    r = client.post("/api/v1/alerts/departure-plan", json={
        "schedule": {"title": "x", "category": "etc", "start_time": "25:99"},
        "context": {}, "user_preference": {},
    })
    assert r.status_code == 200
    assert r.json()["data"]["leave_time"] is None
