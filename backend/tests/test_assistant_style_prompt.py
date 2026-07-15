"""assistant_style_service — LLM 프롬프트용 스타일 지시문 테스트.

style_instruction / styled_system 이 tone·length·reminder_strength 를
자연어 지시문으로 변환하고, raw prefs 와 정규화 profile 을 모두 받는지 검증.
"""

from backend.services import assistant_style_service as style


def test_raw_prefs_short_friendly_strong():
    prefs = {"assistant_tone": "friendly", "response_length": "short",
             "reminder_strength": "strong"}
    s = style.style_instruction(prefs)
    assert "[응답 스타일]" in s
    assert "짧게" in s        # length=short
    assert "친근" in s        # tone=friendly
    assert ("강조" in s or "리마인드" in s)  # strength=strong


def test_profile_formal_long_gentle():
    profile = {"tone": "formal", "length": "long", "strength": "gentle"}
    s = style.style_instruction(profile)
    assert "격식" in s        # formal
    assert "자세" in s        # long
    assert "부드럽게" in s     # gentle


def test_empty_uses_defaults():
    s = style.style_instruction({})
    # 기본값: friendly / medium / normal
    assert "친근" in s
    assert "2~3문장" in s


def test_styled_system_appends_to_base():
    base = "너는 일정 비서야."
    out = style.styled_system(base, {"assistant_tone": "concise"})
    assert out.startswith(base)
    assert "[응답 스타일]" in out
    assert "간결" in out


def test_styled_system_empty_base_is_instruction_only():
    prefs = {"assistant_tone": "caring"}
    assert style.styled_system("", prefs) == style.style_instruction(prefs)
    assert style.styled_system(None, prefs) == style.style_instruction(prefs)


def test_before_after_demo(capsys):
    """스타일 적용 전/후 system 프롬프트 비교 출력(문서용)."""
    base = "너는 사용자의 하루를 정리하는 한국어 비서야. 2~3문장으로 요약해."
    prefs = {"assistant_tone": "friendly", "response_length": "short",
             "reminder_strength": "strong"}
    after = style.styled_system(base, prefs)
    assert base in after and len(after) > len(base)
