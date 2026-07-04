"""LLM integration behavior.

Without a key -> services use templates (default).
With LLM available (patched) -> generation endpoints use the LLM text,
while emotion classification/score and crisis handling stay rule-based.
"""

import backend.services.briefing_generator as bg
import backend.services.emotion_analyzer as ea
import backend.services.message_generator as mg


def test_briefing_uses_llm_summary_when_available(monkeypatch, client):
    monkeypatch.setattr(bg.llm_service, "generate", lambda *a, **k: "LLM이 만든 하루 요약입니다.")
    r = client.post("/api/v1/briefings/daily", json={
        "date": "2026-06-30",
        "schedules": [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}],
        "todos": [],
    })
    data = r.json()["data"]
    assert data["summary"] == "LLM이 만든 하루 요약입니다."
    # priority_order/key_points remain rule-based
    assert data["priority_order"][0]["title"] == "병원 예약"


def test_briefing_falls_back_when_llm_fails(monkeypatch, client):
    def boom(*a, **k):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(bg.llm_service, "generate", boom)
    r = client.post("/api/v1/briefings/daily", json={
        "date": "2026-06-30",
        "schedules": [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}],
        "todos": [],
    })
    assert r.status_code == 200
    assert r.json()["data"]["summary"]  # template summary present


def test_emotion_uses_llm_coaching_but_keeps_rule_label(monkeypatch, client):
    monkeypatch.setattr(ea.llm_service, "generate", lambda *a, **k: "오늘은 충분히 쉬어가도 좋아 보입니다.")
    r = client.post("/api/v1/emotion/analyze", json={
        "input": "오늘 너무 피곤하고 아무것도 하기 싫어",
        "recent_context": {"sleep_hours": 4.5, "schedule_count": 5, "todo_done_rate": 30},
    })
    data = r.json()["data"]
    assert data["coaching"] == "오늘은 충분히 쉬어가도 좋아 보입니다."
    assert data["emotion"] == "fatigue"          # rule-based
    assert data["emotion_score"] == 0.88         # rule-based


def test_emotion_crisis_bypasses_llm(monkeypatch, client):
    monkeypatch.setattr(ea.llm_service, "generate", lambda *a, **k: "should not be used")
    r = client.post("/api/v1/emotion/analyze", json={"input": "다 사라지고 싶어", "recent_context": {}})
    data = r.json()["data"]
    assert data["risk_level"] == "high"
    assert "should not be used" not in data["coaching"]
    assert "전문가" in data["coaching"]


def test_message_uses_llm_when_available(monkeypatch, client):
    monkeypatch.setattr(mg.llm_service, "generate", lambda *a, **k: "LLM 예약 문의 메시지")
    r = client.post("/api/v1/messages/reservation", json={
        "reservation_info": {"category": "hospital", "target_date": "2026-06-30", "preferred_time": "10:00", "purpose": "진료 예약"},
    })
    data = r.json()["data"]
    assert data["generated_message"] == "LLM 예약 문의 메시지"
    assert len(data["alternatives"]) == 2  # alternatives stay template-based
