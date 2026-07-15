"""Lightweight tests for backend/services/qwen7b_vision_analyzer.py.

Does NOT load the real 7B model (that takes minutes and needs a GPU + the
downloaded weights -- exercised manually/in the Stage 1+ real-image checks,
not in the unit test suite). These tests cover: model identity is never
mislabeled, prompts are well-formed, and health_check() fails gracefully
(never crashes, never claims loaded=True falsely) when the model can't load.
"""

import pytest

from backend.services.qwen7b_vision_analyzer import (
    DEFAULT_ENGINE_VARIANT,
    KNOWN_ENGINE_VARIANTS,
    MODEL_ID,
    Qwen7BVisionAnalyzer,
    build_prompt,
)


def test_model_id_is_the_real_7b_not_the_3b_awq():
    """Guards against ever silently substituting qwen_awq (3B AWQ) for this
    engine -- this is the one constant this whole task depends on being honest."""
    assert MODEL_ID == "Qwen/Qwen2.5-VL-7B-Instruct"
    assert "3B" not in MODEL_ID
    assert "AWQ" not in MODEL_ID


def test_build_prompt_water_mentions_only_real_schema_values():
    prompt = build_prompt("water")
    assert "visible_clear_liquid" in prompt
    assert "empty_container" in prompt
    assert "non_water_beverage" in prompt
    # forbidden: the model must never be asked to return a decision
    assert "verified" in prompt  # present only in the explicit prohibition sentence
    assert "Do not include verified" in prompt


def test_build_prompt_study_and_exercise_have_distinct_content():
    study = build_prompt("study")
    exercise = build_prompt("exercise")
    assert "open_textbook" in study
    assert "gaming_content" in study
    assert "yoga_mat_present" in exercise
    assert "gym_environment" in exercise
    assert study != exercise


def test_build_prompt_unknown_task_raises():
    with pytest.raises(ValueError):
        build_prompt("not_a_real_task")


def test_health_check_fails_gracefully_never_crashes_never_fakes_loaded():
    """An intentionally-invalid model id fails fast (no real download) so this
    stays a fast unit test while still exercising the real failure path."""
    analyzer = Qwen7BVisionAnalyzer(model_id="this-model-id-does-not-exist-xyz/nope")
    status = analyzer.health_check()
    assert status["loaded"] is False
    assert status["model_id"] == "this-model-id-does-not-exist-xyz/nope"
    assert status["error"] != ""
    assert analyzer.available() is False


def test_analyze_returns_unavailable_analysis_not_a_crash_when_unloaded():
    analyzer = Qwen7BVisionAnalyzer(model_id="this-model-id-does-not-exist-xyz/nope")
    result = analyzer.analyze("some/fake/path.jpg", "water", ["cup", "glass"])
    assert result.quality.usable is False
    assert any("failed to load" in i for i in result.quality.issues)


def test_default_engine_variant_is_reference_fp32_not_the_nogo_quantized_one():
    """Phase 12: the experimental bnb-nf4 engine is documented NO-GO on this
    GPU (see qwen_recovery/qwen7b_quantized_engine_report.md) and must never
    become the default even though it stays selectable for other hardware."""
    assert DEFAULT_ENGINE_VARIANT == "reference_fp32"
    analyzer = Qwen7BVisionAnalyzer(model_id="this-model-id-does-not-exist-xyz/nope")
    assert analyzer.engine == "reference_fp32"


def test_unknown_engine_variant_rejected():
    with pytest.raises(ValueError):
        Qwen7BVisionAnalyzer(model_id="whatever", engine="not_a_real_engine")


def test_health_check_reports_engine_variant_and_quantization_fields():
    analyzer = Qwen7BVisionAnalyzer(model_id="this-model-id-does-not-exist-xyz/nope",
                                     engine="reference_fp32")
    status = analyzer.health_check()
    assert status["engine_variant"] == "reference_fp32"
    assert status["is_default_engine_variant"] is True
    assert status["quantization"] == "none_fp32"
    assert status["parameter_size"] == "7B"
    assert status["model_family"] == "Qwen2.5-VL"
    assert status["image_input_supported"] is True


def test_quantized_bnb_nf4_is_selectable_but_not_default():
    assert "quantized_bnb_nf4" in KNOWN_ENGINE_VARIANTS
    analyzer = Qwen7BVisionAnalyzer(model_id="this-model-id-does-not-exist-xyz/nope",
                                     engine="quantized_bnb_nf4")
    status = analyzer.health_check()
    assert status["engine_variant"] == "quantized_bnb_nf4"
    assert status["is_default_engine_variant"] is False
    assert status["quantization"] == "bitsandbytes_nf4"
