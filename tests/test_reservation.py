def _payload(existing):
    return {
        "constraints": {"target_date": "2026-07-03", "preferred_start_time": "18:00",
                        "preferred_end_time": "21:00", "duration_minutes": 60, "category": "beauty"},
        "existing_schedules": existing,
    }


def test_candidates_found(client):
    r = client.post("/api/v1/reservations/candidates", json=_payload([
        {"id": "sch_101", "title": "팀플 회의", "date": "2026-07-03", "start_time": "18:00", "end_time": "19:00"},
        {"id": "sch_102", "title": "저녁 약속", "date": "2026-07-03", "start_time": "20:00", "end_time": "21:00"},
    ]))
    assert r.status_code == 200
    data = r.json()["data"]
    assert "recommended_candidates" in data
    assert len(data["recommended_candidates"]) >= 1
    top = data["recommended_candidates"][0]
    assert top["start_time"] == "19:00" and top["conflict"] is False
    assert len(data["rejected_slots"]) == 2


def test_no_available_slot_returns_empty(client):
    r = client.post("/api/v1/reservations/candidates", json=_payload([
        {"id": "x", "title": "종일 워크숍", "date": "2026-07-03", "start_time": "18:00", "end_time": "21:00"},
    ]))
    body = r.json()
    assert body["success"] is True
    assert body["data"]["recommended_candidates"] == []
    assert body["message"] == "예약 가능한 시간이 없습니다."
