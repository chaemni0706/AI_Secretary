"""Phase 11.C: each escalation reason must be reported honestly and distinctly
-- previously every escalation was mislabeled 'smol_not_confident_alone' even
when Smol was actually unavailable/parser-failed/inference-errored."""

from backend.database.schema.image_verification_schema import ImageQuality, VisionAnalysis
from backend.services.image_verification_service import _smol_fallback_reason


def _analysis(usable, issues):
    return VisionAnalysis(quality=ImageQuality(usable=usable, issues=issues))


def test_smol_unavailable_when_not_loaded():
    a = _analysis(False, ["Local VLM 'smolvlm' is not loaded."])
    assert _smol_fallback_reason(a) == "smol_unavailable"


def test_smol_unavailable_when_failed_to_load():
    a = _analysis(False, ["Qwen7B (some/id) failed to load: OSError"])
    assert _smol_fallback_reason(a) == "smol_unavailable"


def test_smol_parser_failure():
    a = _analysis(False, ["Local VLM output could not be parsed."])
    assert _smol_fallback_reason(a) == "smol_parser_failure"


def test_smol_inference_error():
    a = _analysis(False, ["Qwen7B inference error: RuntimeError: CUDA out of memory"])
    assert _smol_fallback_reason(a) == "smol_inference_error"


def test_smol_analysis_failed_counts_as_inference_error():
    a = _analysis(False, ["Local VLM analysis failed: ValueError"])
    assert _smol_fallback_reason(a) == "smol_inference_error"


def test_smol_not_confident_alone_when_usable_but_weak():
    """Smol ran fine (quality.usable=True) but produced no/weak evidence --
    this is the genuine 'ran, just not confident' case, distinct from any
    infra failure."""
    a = _analysis(True, [])
    assert _smol_fallback_reason(a) == "smol_not_confident_alone"


def test_unusable_with_unrecognized_issue_defaults_to_not_confident_alone():
    """An unusable analysis whose issue text doesn't match any known infra
    marker still needs a reason string -- falls back to the generic label
    rather than crashing or mislabeling as a specific category it doesn't
    match."""
    a = _analysis(False, ["some unrecognized future issue string"])
    assert _smol_fallback_reason(a) == "smol_not_confident_alone"
