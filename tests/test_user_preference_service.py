"""backend/services/user_preference_service.py — in-memory rule-based
AI voice-response preference store (assistant_tone/response_length/nudge_strength).
No LLM, no DB in the MVP; interface is designed so storage can swap to SQLite later.
"""

import pytest

from backend.services import user_preference_service as svc


@pytest.fixture(autouse=True)
def _isolate_store():
    """Each test gets a clean in-memory store (module-level dict)."""
    svc._STORE.clear()
    yield
    svc._STORE.clear()


# --------------------------------------------------------------------------- #
# 1. defaults
# --------------------------------------------------------------------------- #
def test_default_preferences_are_friendly_normal_medium():
    defaults = svc.get_default_preferences()
    assert defaults == {
        "assistant_tone": "friendly",
        "response_length": "normal",
        "nudge_strength": "medium",
        "briefing_time": "",
    }


def test_unknown_user_gets_defaults():
    assert svc.get_user_preferences("brand-new-user") == svc.get_default_preferences()


def test_none_user_id_falls_back_to_local_user():
    svc.update_user_preferences(None, {"assistant_tone": "caring"})
    assert svc.get_user_preferences("local-user")["assistant_tone"] == "caring"


# --------------------------------------------------------------------------- #
# 2. partial update keeps the rest
# --------------------------------------------------------------------------- #
def test_partial_update_keeps_other_axes():
    svc.update_user_preferences("u1", {"assistant_tone": "concise"})
    prefs = svc.get_user_preferences("u1")
    assert prefs["assistant_tone"] == "concise"
    assert prefs["response_length"] == "normal"
    assert prefs["nudge_strength"] == "medium"

    svc.update_user_preferences("u1", {"response_length": "short"})
    prefs = svc.get_user_preferences("u1")
    assert prefs == {
        "assistant_tone": "concise",
        "response_length": "short",
        "nudge_strength": "medium",
        "briefing_time": "",
    }


# --------------------------------------------------------------------------- #
# 3. invalid values are safely ignored (never raise)
# --------------------------------------------------------------------------- #
def test_invalid_assistant_tone_falls_back_to_default():
    result = svc.update_user_preferences("u2", {"assistant_tone": "angry"})
    assert result["assistant_tone"] == "friendly"


def test_invalid_value_does_not_overwrite_previously_valid_one():
    svc.update_user_preferences("u3", {"assistant_tone": "professional"})
    result = svc.update_user_preferences("u3", {"assistant_tone": "not-a-real-tone"})
    assert result["assistant_tone"] == "professional"


def test_unknown_keys_are_ignored():
    result = svc.update_user_preferences("u4", {"favorite_color": "blue"})
    assert "favorite_color" not in result


def test_normalize_preference_value():
    assert svc.normalize_preference_value("assistant_tone", "caring") == "caring"
    assert svc.normalize_preference_value("assistant_tone", "not-real") is None
    assert svc.normalize_preference_value("assistant_tone", None) is None
    assert svc.normalize_preference_value("no_such_category", "x") is None


def test_validate_preferences_drops_invalid_keeps_valid():
    cleaned = svc.validate_preferences(
        {"assistant_tone": "caring", "response_length": "nope", "extra": 1}
    )
    assert cleaned == {"assistant_tone": "caring"}
    assert svc.validate_preferences("not a dict") == {}


# --------------------------------------------------------------------------- #
# options (for the Flutter settings screen)
# --------------------------------------------------------------------------- #
def test_get_options_covers_all_three_axes_with_display_names():
    options = svc.get_options()
    assert set(options.keys()) == {"assistant_tone", "response_length", "nudge_strength"}
    assert len(options["assistant_tone"]) == 5
    assert len(options["response_length"]) == 3
    assert len(options["nudge_strength"]) == 3
    for opt in options["assistant_tone"]:
        assert set(opt.keys()) == {"code", "display_name"}
        assert opt["display_name"]


# --------------------------------------------------------------------------- #
# briefing_time (additive) — 'HH:mm' 자동 브리핑 시각, ""는 비활성화
# --------------------------------------------------------------------------- #
def test_briefing_time_accepts_valid_hhmm():
    prefs = svc.update_user_preferences("u2", {"briefing_time": "08:30"})
    assert prefs["briefing_time"] == "08:30"


def test_briefing_time_rejects_invalid_value_keeps_previous():
    svc.update_user_preferences("u3", {"briefing_time": "08:30"})
    prefs = svc.update_user_preferences("u3", {"briefing_time": "not-a-time"})
    assert prefs["briefing_time"] == "08:30"


def test_briefing_time_empty_string_disables():
    svc.update_user_preferences("u4", {"briefing_time": "08:30"})
    prefs = svc.update_user_preferences("u4", {"briefing_time": ""})
    assert prefs["briefing_time"] == ""


def test_briefing_time_not_provided_leaves_other_axes_untouched():
    svc.update_user_preferences("u5", {"briefing_time": "07:00"})
    prefs = svc.update_user_preferences("u5", {"assistant_tone": "caring"})
    assert prefs["briefing_time"] == "07:00"
    assert prefs["assistant_tone"] == "caring"
