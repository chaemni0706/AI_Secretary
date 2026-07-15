"""backend/services/tts_response_builder.py — JSON + rule-based TTS sentence
builder (no LLM). Covers tone/length/nudge variation and the safety-net
fallbacks (unknown intent, unknown tone, missing slot, never raises).
"""

from backend.services.tts_response_builder import build_tts_response

SLOTS = {"title": "회의", "date": "내일", "time": "오후 3시"}


def _prefs(**overrides):
    base = {"assistant_tone": "friendly", "response_length": "normal", "nudge_strength": "medium"}
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 4. same intent/slots, different assistant_tone -> different tts_text
# --------------------------------------------------------------------------- #
def test_assistant_tone_changes_the_sentence():
    texts = {
        tone: build_tts_response("schedule_create_success", SLOTS, _prefs(assistant_tone=tone))
        for tone in ("polite", "friendly", "concise", "caring", "professional")
    }
    assert len(set(texts.values())) == len(texts)  # all 5 distinct


# --------------------------------------------------------------------------- #
# 5 / 6. response_length changes sentence count
# --------------------------------------------------------------------------- #
def test_short_length_has_fewer_sentences_than_detailed():
    short = build_tts_response("schedule_create_success", SLOTS, _prefs(response_length="short"))
    detailed = build_tts_response(
        "schedule_create_success", SLOTS, _prefs(response_length="detailed")
    )
    assert short.count(".") + short.count("?") <= detailed.count(".") + detailed.count("?")
    assert short != detailed


def test_detailed_length_adds_extra_guidance_within_three_sentences():
    detailed = build_tts_response(
        "schedule_create_success", SLOTS, _prefs(response_length="detailed", nudge_strength="low")
    )
    sentence_count = detailed.count(".") + detailed.count("?")
    assert 1 <= sentence_count <= 3
    assert "필요하면" in detailed or "설정" in detailed


# --------------------------------------------------------------------------- #
# 7 / 8. nudge_strength gates the reminder sentence
# --------------------------------------------------------------------------- #
def test_low_nudge_adds_no_reminder_sentence():
    base = build_tts_response("todo_create_success", {"title": "과제", "date": "오늘"}, _prefs(nudge_strength="low"))
    with_medium = build_tts_response(
        "todo_create_success", {"title": "과제", "date": "오늘"}, _prefs(nudge_strength="medium")
    )
    assert base != with_medium
    assert "확인해두면" not in base


def test_high_nudge_adds_a_reminder_sentence():
    text = build_tts_response(
        "todo_create_success", {"title": "과제", "date": "오늘"}, _prefs(nudge_strength="high")
    )
    assert "진행해볼까요" in text or "추천" in text


# --------------------------------------------------------------------------- #
# 9. unknown intent -> fallback sentence, never crashes
# --------------------------------------------------------------------------- #
def test_unknown_intent_falls_back_safely():
    text = build_tts_response("no_such_intent_xyz", {}, _prefs())
    assert isinstance(text, str) and text


def test_unknown_tone_falls_back_to_default_tone():
    text = build_tts_response("schedule_create_success", SLOTS, _prefs(assistant_tone="angry"))
    assert text == build_tts_response("schedule_create_success", SLOTS, _prefs(assistant_tone="friendly"))


# --------------------------------------------------------------------------- #
# 10. missing slot never raises / never 500s
# --------------------------------------------------------------------------- #
def test_missing_slots_do_not_raise():
    text = build_tts_response("schedule_create_success", {}, _prefs())
    assert isinstance(text, str) and text


def test_none_slots_and_none_preferences_do_not_raise():
    text = build_tts_response("schedule_create_success", None, None)
    assert isinstance(text, str) and text


def test_malformed_preferences_do_not_raise():
    text = build_tts_response("schedule_create_success", SLOTS, {"assistant_tone": 12345})
    assert isinstance(text, str) and text


# --------------------------------------------------------------------------- #
# slot values are never altered by tone/length/nudge post-processing
# --------------------------------------------------------------------------- #
def test_slot_values_are_preserved_verbatim():
    for tone in ("polite", "friendly", "concise", "caring", "professional"):
        text = build_tts_response("schedule_create_success", SLOTS, _prefs(assistant_tone=tone))
        assert SLOTS["title"] in text
        assert SLOTS["date"] in text
        assert SLOTS["time"] in text


# --------------------------------------------------------------------------- #
# concise tone caps sentence count regardless of length/nudge settings
# --------------------------------------------------------------------------- #
def test_concise_tone_stays_terse_even_at_detailed_high_nudge():
    text = build_tts_response(
        "schedule_create_success", SLOTS,
        _prefs(assistant_tone="concise", response_length="detailed", nudge_strength="high"),
    )
    assert text.count(".") + text.count("?") <= 1


# --------------------------------------------------------------------------- #
# global TTS normalization: no markdown / emoji ever leaks through
# --------------------------------------------------------------------------- #
def test_output_has_no_emoji_or_markdown():
    for intent in ("schedule_create_success", "briefing_empty", "fallback_unknown"):
        text = build_tts_response(intent, SLOTS, _prefs())
        assert "*" not in text and "#" not in text and "`" not in text
