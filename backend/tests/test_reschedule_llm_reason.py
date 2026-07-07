"""reschedule_recommender — 계산은 규칙, 설명 문장만 LLM 검증.

핵심: LLM 사용 여부와 무관하게 title/score/시각/후보 개수(=계산 결과)는 동일해야
하고, LLM이 켜졌을 때만 '최상위 후보의 reason 문장'이 바뀐다.
실제 OpenAI 호출은 monkeypatch 로 대체한다.
"""

import pytest

from backend.services import reschedule_recommender as RR

CTX = {
    "current_time": "2026-07-01T09:00:00",
    "today_schedule": [
        {
            "id": "t1", "title": "과제", "category": "study", "priority": "low",
            "start_time": "2026-07-01T13:00:00", "end_time": "2026-07-01T14:00:00",
        }
    ],
}


def test_rule_only_produces_candidates():
    out = RR.recommend(CTX)
    assert out, "규칙만으로 후보가 생성되어야 함"
    assert out[0]["reason"].strip()
    # 규칙 reason 은 계산 근거 문구를 포함
    assert "충돌" in out[0]["reason"]


def test_llm_off_keeps_rule_reason(monkeypatch):
    monkeypatch.setattr(RR.settings, "ENABLE_LLM_RESCHEDULE", False)
    called = {"n": 0}
    monkeypatch.setattr(RR, "_llm_reason", lambda c, n: called.__setitem__("n", 1))
    out = RR.recommend(CTX)
    assert "충돌" in out[0]["reason"]
    assert called["n"] == 0  # LLM 미호출


def test_llm_on_replaces_only_top_reason(monkeypatch):
    # 기준선: 규칙만 (LLM off)
    monkeypatch.setattr(RR.settings, "ENABLE_LLM_RESCHEDULE", False)
    base = RR.recommend(CTX)
    # LLM on
    monkeypatch.setattr(RR.settings, "ENABLE_LLM_RESCHEDULE", True)
    monkeypatch.setattr(RR.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(RR.llm_service, "generate",
                        lambda *a, **k: "오늘 일정이 몰려 있어서 이 시간에 진행하는 걸 추천해요.")
    out = RR.recommend(CTX)

    # 최상위 reason 은 LLM 문장으로 교체
    assert out[0]["reason"] == "오늘 일정이 몰려 있어서 이 시간에 진행하는 걸 추천해요."
    # 계산 결과(제목/점수/후보 수)는 규칙과 동일 — LLM이 계산을 건드리지 않음
    assert [c["title"] for c in out] == [c["title"] for c in base]
    assert [c["score"] for c in out] == [c["score"] for c in base]
    # 2번째 이후 후보의 reason 은 규칙 그대로
    if len(out) > 1:
        assert "충돌" in out[1]["reason"]


def test_llm_too_long_keeps_rule(monkeypatch):
    monkeypatch.setattr(RR.settings, "ENABLE_LLM_RESCHEDULE", True)
    monkeypatch.setattr(RR.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(RR.llm_service, "generate", lambda *a, **k: "가" * 300)
    out = RR.recommend(CTX)
    assert "충돌" in out[0]["reason"]  # 길이 초과 → 규칙 유지


def test_llm_failure_keeps_rule(monkeypatch):
    monkeypatch.setattr(RR.settings, "ENABLE_LLM_RESCHEDULE", True)
    monkeypatch.setattr(RR.llm_service, "is_enabled", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(RR.llm_service, "generate", boom)
    out = RR.recommend(CTX)
    assert "충돌" in out[0]["reason"]
