"""Unit tests for backend/services/qwen_evidence_parser.py.

No model call -- pure string/JSON parsing tests against the real
VisionAnalysis schema (water/study/exercise Literal enums).
"""

from backend.services import qwen_evidence_parser as parser


def test_strip_code_fences_removes_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert parser.strip_code_fences(raw) == '{"a": 1}'


def test_strip_code_fences_removes_plain_fence():
    raw = '```\n{"a": 1}\n```'
    assert parser.strip_code_fences(raw) == '{"a": 1}'


def test_strip_code_fences_noop_without_fence():
    raw = '{"a": 1}'
    assert parser.strip_code_fences(raw) == raw


def test_extract_json_object_finds_balanced_object_with_prose():
    text = 'Sure, here is the JSON:\n{"a": {"b": 1}, "c": [1,2,3]}\nHope that helps!'
    extracted = parser.extract_json_object(text)
    assert extracted == '{"a": {"b": 1}, "c": [1,2,3]}'


def test_extract_json_object_none_when_no_brace():
    assert parser.extract_json_object("no json here") is None


def test_extract_json_object_handles_braces_inside_strings():
    text = '{"note": "a } inside a string", "x": 1}'
    extracted = parser.extract_json_object(text)
    assert extracted == text


def test_parse_clean_water_response():
    raw = (
        '{"task": "water", "evidence": ["visible_water", "filled_container"], '
        '"blockers": [], "uncertainty": "low", "scene_complexity": "simple", '
        '"model_name": "Qwen/Qwen2.5-VL-7B-Instruct"}'
    )
    analysis, status, diag = parser.parse_qwen_response(raw, "water")
    assert status == "clean"
    assert analysis is not None
    assert set(analysis.water_visual_evidence) == {"visible_water", "filled_container"}
    assert analysis.blockers == []
    assert analysis.uncertainty == "low"
    assert diag["unmapped_tags"] == []


def test_parse_maps_alias_tag_names():
    """Task brief draft tag names (e.g. clear_liquid_visible) must map onto the
    real WaterVisualEvidence enum, not be dropped or left as invalid values."""
    raw = '{"task": "water", "evidence": ["clear_liquid_visible", "liquid_level_visible"], "blockers": []}'
    analysis, status, diag = parser.parse_qwen_response(raw, "water")
    assert status == "clean"
    assert "visible_clear_liquid" in analysis.water_visual_evidence
    assert "filled_container" in analysis.water_visual_evidence


def test_parse_keeps_unknown_tags_in_visual_evidence_not_dropped():
    raw = '{"task": "water", "evidence": ["totally_unknown_tag_xyz"], "blockers": []}'
    analysis, status, diag = parser.parse_qwen_response(raw, "water")
    assert status == "clean"
    assert "totally_unknown_tag_xyz" not in (analysis.water_visual_evidence or [])
    assert "totally_unknown_tag_xyz" in analysis.visual_evidence
    assert "totally_unknown_tag_xyz" in diag["unmapped_tags"]


def test_parse_blockers_populate_both_task_field_and_blockers_field():
    raw = '{"task": "water", "evidence": [], "blockers": ["empty_container"]}'
    analysis, status, _diag = parser.parse_qwen_response(raw, "water")
    assert status == "clean"
    assert "empty_container" in analysis.water_visual_evidence
    assert "empty_container" in analysis.blockers


def test_parse_key_aliases_normalize():
    raw = '{"task": "study", "evidences": ["open_textbook"], "blocker": ["gaming_content"], "confidence": "high"}'
    analysis, status, _diag = parser.parse_qwen_response(raw, "study")
    assert status == "clean"
    assert "open_textbook" in analysis.study_visual_evidence
    assert "gaming_content" in analysis.blockers
    assert analysis.uncertainty == "high"


def test_parse_failed_on_empty_response():
    analysis, status, diag = parser.parse_qwen_response("", "water")
    assert analysis is None
    assert status == "failed"
    assert diag["error"] == "empty_response"


def test_parse_failed_on_no_json_object():
    analysis, status, diag = parser.parse_qwen_response("I cannot determine this.", "water")
    assert analysis is None
    assert status == "failed"


def test_parse_failed_on_malformed_json():
    analysis, status, diag = parser.parse_qwen_response('{"task": "water", "evidence": [}', "water")
    assert analysis is None
    assert status == "failed"
    assert "json_decode_error" in diag["error"]


def test_parse_never_trusts_a_decision_field_even_if_present():
    """The model must not be able to smuggle a decision through -- the parser
    doesn't even have a slot for it, so it's silently absent from the result
    regardless of what the raw text contains."""
    raw = '{"task": "water", "evidence": ["visible_water", "filled_container"], "result": "verified"}'
    analysis, status, _diag = parser.parse_qwen_response(raw, "water")
    assert status == "clean"
    assert not hasattr(analysis, "result")


def test_build_repair_prompt_contains_original_and_allowed_values():
    prompt = parser.build_repair_prompt('{"broken"', "study", "json_decode_error: x")
    assert "broken" in prompt
    assert "open_textbook" in prompt
    assert "verified" in prompt  # explicit prohibition text must be present


def test_contradictory_exercise_environments_forces_high_uncertainty():
    """Real bug found in Phase 11 E2E testing: the model reported gym +
    swimming pool + yoga studio + pilates studio simultaneously for one
    photo. This must never be trusted as low-uncertainty evidence."""
    raw = (
        '{"task": "exercise", "evidence": ["gym_environment", "dumbbell_present", '
        '"swimming_pool_environment", "yoga_studio_present", "pilates_studio_present"], '
        '"blockers": [], "uncertainty": "low"}'
    )
    analysis, status, diag = parser.parse_qwen_response(raw, "exercise")
    assert status == "clean"
    assert analysis.uncertainty == "high"  # forced up despite model claiming "low"
    assert diag.get("contradictory_scene_evidence") is True


def test_single_exercise_environment_keeps_reported_uncertainty():
    raw = '{"task": "exercise", "evidence": ["gym_environment", "dumbbell_present"], "blockers": [], "uncertainty": "low"}'
    analysis, status, diag = parser.parse_qwen_response(raw, "exercise")
    assert status == "clean"
    assert analysis.uncertainty == "low"
    assert "contradictory_scene_evidence" not in diag
