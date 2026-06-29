"""General API contract tests: health + common envelope on every endpoint."""


def _check_envelope(body):
    assert set(["success", "message", "data"]).issubset(body.keys())
    assert isinstance(body["success"], bool)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    _check_envelope(body)
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_unknown_route_returns_common_error(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    _check_envelope(body)
    assert body["success"] is False


def test_all_endpoints_return_data(client):
    calls = [
        ("/api/v1/ai/schedule/parse", {"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": "2026-06-29T10:00:00+09:00"}),
        ("/api/v1/reservations/candidates", {"constraints": {"target_date": "2026-07-03", "preferred_start_time": "18:00", "preferred_end_time": "21:00", "duration_minutes": 60}, "existing_schedules": []}),
        ("/api/v1/messages/reservation", {"reservation_info": {"category": "hospital", "target_date": "2026-06-30", "preferred_time": "10:00", "purpose": "진료 예약"}}),
        ("/api/v1/alerts/departure-plan", {"schedule": {"title": "병원 예약", "category": "hospital", "start_time": "14:00"}, "context": {"estimated_travel_minutes": 35, "buffer_minutes": 10}}),
        ("/api/v1/briefings/daily", {"date": "2026-06-30", "schedules": [], "todos": []}),
        ("/api/v1/emotion/analyze", {"input": "오늘 너무 피곤해", "recent_context": {}}),
    ]
    for path, payload in calls:
        r = client.post(path, json=payload)
        assert r.status_code == 200, path
        body = r.json()
        _check_envelope(body)
        assert body["success"] is True, path
        assert body["data"] is not None, path
