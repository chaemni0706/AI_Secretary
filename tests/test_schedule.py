NOW = "2026-06-29T10:00:00+09:00"


def test_parse_valid(client):
    r = client.post("/api/v1/ai/schedule/parse",
                    json={"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": NOW})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["intent"] == "create_schedule"
    assert "schedule_draft" in data
    assert data["schedule_draft"]["category"] == "hospital"
    assert data["slots"]["date"] == "2026-06-30"
    assert data["slots"]["start_time"] == "14:00"
    assert data["missing_fields"] == []


def test_parse_empty_input_reports_missing(client):
    r = client.post("/api/v1/ai/schedule/parse", json={"input": "", "current_datetime": NOW})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert "date" in data["missing_fields"]
    assert "start_time" in data["missing_fields"]


def test_parse_time_ambiguity(client):
    r = client.post("/api/v1/ai/schedule/parse",
                    json={"input": "7월 3일 3시에 미용실 예약 넣어줘", "current_datetime": NOW})
    data = r.json()["data"]
    assert "time_ambiguity" in data["missing_fields"]
    assert data["slots"]["category"] == "beauty"
