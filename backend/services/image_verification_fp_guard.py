"""Backend FP guard -- a single choke point applied AFTER the Rule Engine,
vetoing `verified` only when explicit, structured contradictory evidence is
present. Never a decision-maker on its own: it can only downgrade
`verified` -> `retake_required`; it never touches `rejected`/`retake_required`
results and never produces `verified`.

Why this is NOT a copy of local_eval/vlm_baseline/vlm_fp_guard.py (per this
task's explicit instruction to check evidence-schema/GT dependence first,
not copy blindly):

  1. That module scans a free-text `reason` string against hardcoded keyword
     lists ("yellow", "coffee", "opaque", ...) because its evidence source
     (A.X/Qwen mini-probe harness) only reliably exposed a natural-language
     reason field -- its own comment notes the *structured*
     positive_evidence/negative_evidence fields were "vocabulary-dump,
     unreliable" for that harness.
  2. This production pipeline's evidence is NOT a natural-language dump --
     it is validated, canonical Literal-enum evidence
     (water_visual_evidence/study_visual_evidence/exercise_visual_evidence,
     backend/database/schema/image_verification_schema.py), produced by
     backend/services/qwen_evidence_parser.py specifically so this guard can
     check structured values instead of scanning text.
  3. That module's `_WATER_NEG`/`_EX_NEG` keyword lists were tuned against a
     specific evaluation harness's free-text outputs (mini_probe48). Nothing
     here is tuned against any dataset's ground truth -- every value checked
     below is a value that already exists in the real schema/rule engine
     (`_priority_result` in image_verification_rule_engine.py), not
     something fit to this task's or any dataset's FP outcomes.

CRITICAL CONSTRAINT: at inference time there is no gt_label, no manifest,
no "VLM-eligible visual scope" annotation, no dataset identity at all. This
guard must never reference any of those (they don't exist outside offline
evaluation scripts). It reads only the same `VisionAnalysis` object the Rule
Engine already scored.
"""

from __future__ import annotations

from backend.database.schema.image_verification_schema import (
    ImageVerificationData,
    VerificationType,
    VisionAnalysis,
)

# Explicit contradictory-evidence value sets, per task -- copied from the
# values `image_verification_rule_engine.py::_priority_result` already
# treats as confident negatives (not new/invented values). Kept here as an
# independent, explicit list so this guard does not silently drift if the
# Rule Engine's internal priority-code naming changes -- it checks the
# canonical WaterVisualEvidence/StudyVisualEvidence/ExerciseVisualEvidence
# values directly, not the Rule Engine's internal `RuleEvidence.code` strings.
_CONTRADICTORY_EVIDENCE = {
    "water": {"empty_container", "opaque_closed_container", "non_water_beverage", "uncertain_liquid"},
    "study": {"gaming_content", "entertainment_video", "social_media", "shopping_content", "non_study_screen"},
    "exercise": {"unrelated_environment", "wrong_activity_environment", "insufficient_exercise_evidence",
                 "uncertain_exercise_environment"},
}

_TASK_EVIDENCE_FIELD = {
    "water": "water_visual_evidence",
    "study": "study_visual_evidence",
    "exercise": "exercise_visual_evidence",
}


def _task_evidence_values(analysis: VisionAnalysis, verification_type: str) -> set[str]:
    field = _TASK_EVIDENCE_FIELD.get(verification_type)
    if field is None:
        return set()
    return set(getattr(analysis, field, None) or [])


def apply_fp_guard(
    verification_type: VerificationType,
    data: ImageVerificationData,
) -> ImageVerificationData:
    """Only acts on `verified`. Vetoes to `retake_required` when the final
    merged evidence contains an explicit contradiction for this task, or
    when the model itself signalled non-low uncertainty on a verified result.
    Never reads gt_label/manifest/dataset metadata -- only `data.vlm_analysis`."""
    if data.result != "verified":
        return data

    analysis = data.vlm_analysis
    task = str(verification_type)
    contradictions = _CONTRADICTORY_EVIDENCE.get(task, set())

    task_values = _task_evidence_values(analysis, task)
    explicit_blockers = set(analysis.blockers or [])
    hit = (task_values | explicit_blockers) & contradictions
    if hit:
        return data.model_copy(update={
            "result": "retake_required",
            "guard_reason": f"fp_guard:contradictory_evidence:{sorted(hit)}",
        })

    if analysis.uncertainty != "low":
        return data.model_copy(update={
            "result": "retake_required",
            "guard_reason": f"fp_guard:model_reported_uncertainty:{analysis.uncertainty}",
        })

    return data.model_copy(update={"guard_reason": ""})
