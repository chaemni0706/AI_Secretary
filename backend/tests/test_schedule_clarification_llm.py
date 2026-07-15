"""schedule_clarification — LLM 되묻기 문장 + 템플릿 fallback 테스트.

각 상황(날짜 없음 / 시간 없음 / 제목 없음)에 대해:
- LLM 비활성: 기존 템플릿으로 동작(문장 반환)
- LLM 활성 + 성공: LLM 문장을 사용
- LLM 활성 + 길이초과/실패: 템플릿으로 fallback
실제 OpenAI 호출은 monkeypatch 로 대체한다.
"""

import pytest

from backend.services import schedule_clarification as C


def _enable_llm(monkeypatch, fake):
    monkeypatch.setattr(C.settings, "ENABLE_LLM_CLARIFY", True)
    monkeypatch.setattr(C.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(C.llm_service, "generate", fake)


# --------------------------------------------------------------------------- #
# 템플릿 fallback (LLM 비활성) — 각 상황에서 비어있지 않은 문장 반환
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title,missing", [
    ("치과", ["date"]),         # 날짜 없음
    ("치과", ["time"]),         # 시간 없음
    (None, ["title", "date"]),  # 제목 없음
])
def test_template_fallback_when_llm_off(monkeypatch, title, missing):
    monkeypatch.setattr(C.settings, "ENABLE_LLM_CLARIFY", False)
    out = C.build_clarification(category="hospital", title=title, missing_fields=missing)
    assert out["status"] == "needs_clarification"
    assert out["clarification_message"].strip()  # 비어있지 않은 문장
    assert out["tts_text"].strip()


# --------------------------------------------------------------------------- #
# LLM 활성 + 성공 → LLM 문장 사용
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title,missing,canned", [
    ("치과", ["date"], "치과 일정은 며칠로 잡아드릴까요?"),
    ("치과", ["time"], "치과는 몇 시로 예약할까요?"),
    (None, ["title", "date"], "어떤 일정을 언제 등록할까요?"),
])
def test_llm_used_when_enabled(monkeypatch, title, missing, canned):
    _enable_llm(monkeypatch, lambda *a, **k: canned)
    out = C.build_clarification(category="hospital", title=title, missing_fields=missing)
    assert out["clarification_message"] == canned
    assert out["tts_text"] == canned


# --------------------------------------------------------------------------- #
# LLM 활성이지만 결과가 너무 길거나(길이 제한) 실패 → 템플릿 fallback
# --------------------------------------------------------------------------- #
def test_llm_too_long_falls_back(monkeypatch):
    long_text = "가" * 200  # _CLARIFY_MAX_LEN 초과
    _enable_llm(monkeypatch, lambda *a, **k: long_text)
    out = C.build_clarification(category="hospital", title="치과", missing_fields=["date"])
    assert out["clarification_message"] != long_text
    assert out["clarification_message"].strip()


def test_llm_none_falls_back(monkeypatch):
    _enable_llm(monkeypatch, lambda *a, **k: None)  # 키없음/실패 모사
    out = C.build_clarification(category="hospital", title="치과", missing_fields=["time"])
    assert out["clarification_message"].strip()


def test_llm_exception_falls_back(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")
    _enable_llm(monkeypatch, boom)
    out = C.build_clarification(category="hospital", title="치과", missing_fields=["date"])
    assert out["clarification_message"].strip()


# --------------------------------------------------------------------------- #
# 완료(누락 없음) 상황은 LLM 호출 없이 status=success
# --------------------------------------------------------------------------- #
def test_no_missing_is_success(monkeypatch):
    called = {"n": 0}
    _enable_llm(monkeypatch, lambda *a, **k: called.__setitem__("n", 1) or "x")
    out = C.build_clarification(
        category="hospital", title="치과", missing_fields=[],
        date_text="내일", time_text="오후 2시",
    )
    assert out["status"] == "success"
    assert called["n"] == 0  # 누락 없으면 LLM 미호출
