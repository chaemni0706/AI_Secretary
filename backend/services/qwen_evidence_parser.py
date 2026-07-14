"""Parser/normalizer for Qwen7B (and any future full-VLM) evidence JSON.

The model is instructed to return evidence JSON only (task/evidence/blockers/
uncertainty/scene_complexity/parser_version/model_name -- see
backend/services/qwen7b_vision_analyzer.py's prompt). This module turns that
raw text into a validated `VisionAnalysis` (backend/database/schema/
image_verification_schema.py), or fails safely with an explicit
`parse_status` that is never hidden from the caller.

Steps (all deterministic, no model call in this module):
  1. Strip markdown code fences.
  2. Extract the first balanced JSON object from the text (robust to
     leading/trailing prose the model may add despite instructions).
  3. json.loads.
  4. Key-alias normalization (top-level key name variants -> canonical keys).
  5. Enum-alias normalization (per-task evidence tag variants -> the real
     WaterVisualEvidence/StudyVisualEvidence/ExerciseVisualEvidence Literal
     values). Unknown tags are NEVER silently dropped -- they are kept in
     `visual_evidence` (the schema's existing generic catch-all list) and
     recorded in diagnostics.
  6. pydantic validation via VisionAnalysis(**payload).

`parse_qwen_response` never raises; it always returns a
`(VisionAnalysis | None, parse_status, diagnostics)` tuple. Exactly one
repair attempt is the caller's responsibility (see
qwen7b_vision_analyzer.py) -- this module only tells the caller whether the
first attempt succeeded, never retries itself.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from backend.database.schema.image_verification_schema import (
    ExerciseVisualEvidence,
    ImageObjectObservation,
    ImageQuality,
    StudyVisualEvidence,
    VisionAnalysis,
    WaterVisualEvidence,
)

PARSER_VERSION = "qwen_evidence_parser/1.0.0"

ParseStatus = Literal["clean", "repaired", "failed"]

# ---------------------------------------------------------------------------
# canonical enum value sets, read directly from the real schema Literal types
# so this module can never drift from what evaluate_image_verification()
# actually accepts.
# ---------------------------------------------------------------------------
_WATER_VALUES = set(WaterVisualEvidence.__args__)
_STUDY_VALUES = set(StudyVisualEvidence.__args__)
_EXERCISE_VALUES = set(ExerciseVisualEvidence.__args__)

_EVIDENCE_FIELD_BY_TASK = {
    "water": ("water_visual_evidence", _WATER_VALUES),
    "study": ("study_visual_evidence", _STUDY_VALUES),
    "exercise": ("exercise_visual_evidence", _EXERCISE_VALUES),
}

# ---------------------------------------------------------------------------
# tag-name alias tables. Populated from the same corrections documented in
# local_eval/qwen_recovery/qwen_recovery_prompts.yaml's `tag_name_corrections`
# blocks -- this is that mapping actually wired into code, not just docs.
# Keys are lowercased before lookup so case variants normalize too.
# ---------------------------------------------------------------------------
_WATER_ALIASES = {
    "clear_liquid_visible": "visible_clear_liquid",
    "liquid_level_visible": "filled_container",
    "colored_liquid": "non_water_beverage",
    "reflection_or_occlusion": "opaque_closed_container",
    "container_visible": None,  # object-level, not a water_visual_evidence value; dropped from
                                 # this field but the raw tag is preserved in visual_evidence.
}
_STUDY_ALIASES = {
    "open_book": "open_textbook",
    "textbook_or_workbook": "open_textbook",
    "printed_problem": "problem_solving_material",
    "document_with_text": "educational_document",
    "lecture_screen": "lecture_video",
    "coding_screen": "code_editor",
    "pdf_document_screen": "educational_document",
    "entertainment_screen": "entertainment_video",
    "social_media_screen": "social_media",
    "shopping_screen": "shopping_content",
    "uncertain_study_context": "uncertain_screen_content",
    "weak_laptop_only": None,  # derived condition, not a model-reported evidence value
    "desk_only": None,
    "person_only": None,
}
_EXERCISE_ALIASES = {
    "gym_environment_visible": "gym_environment",
    "exercise_equipment_visible": "exercise_equipment_present",
    "yoga_mat_laid_out": "yoga_mat_present",
    "pilates_equipment_visible": "pilates_equipment_present",
    "exercise_space_visible": "exercise_environment",
    "resting_or_sitting": "insufficient_exercise_evidence",
    "sofa_or_bedroom_context": "unrelated_environment",
    "selfie_or_clothes_only": "insufficient_exercise_evidence",
    "uncertain_exercise_context": "uncertain_exercise_environment",
    "person_only": None,  # derived condition (person label + zero positive evidence), not a
                           # model-reported evidence value
}
_ALIASES_BY_TASK = {"water": _WATER_ALIASES, "study": _STUDY_ALIASES, "exercise": _EXERCISE_ALIASES}

# Top-level key aliases -> canonical keys used by this parser's payload dict.
_KEY_ALIASES = {
    "evidences": "evidence",
    "positive_evidence": "evidence",
    "blocker": "blockers",
    "negative_evidence": "blockers",
    "confidence": "uncertainty",
    "certainty": "uncertainty",
    "complexity": "scene_complexity",
    "model": "model_name",
    "objects_detected": "objects",
}

_UNCERTAINTY_VALUES = {"low", "medium", "high"}
_SCENE_COMPLEXITY_VALUES = {"simple", "moderate", "complex"}

# Phase 11.G: a single photo can only genuinely show one of these environments at a time.
# A real image, tested end-to-end, produced gym_environment + swimming_pool_environment +
# yoga_studio_present + pilates_studio_present simultaneously -- the model over-generating
# plausible-but-unseen environment tags. This is a safety-net check independent of prompt
# wording (prompt hygiene alone is not reliable): if 2+ of these mutually-exclusive groups
# fire together, evidence is contradictory and must not be trusted as low-uncertainty.
_EXERCISE_ENV_GROUPS = [
    {"gym_environment"},
    {"running_track_present", "treadmill_running_environment", "stadium_track_present",
     "park_running_path_present"},
    {"swimming_pool_environment"},
    {"yoga_studio_present"},
    {"pilates_studio_present"},
    {"home_workout_environment"},
]


def _has_contradictory_exercise_environments(tags: set[str]) -> bool:
    hit_groups = sum(1 for group in _EXERCISE_ENV_GROUPS if tags & group)
    return hit_groups >= 2


def strip_code_fences(text: str) -> str:
    text = text.strip()
    # ```json ... ``` or ``` ... ```
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def extract_json_object(text: str) -> Optional[str]:
    """Finds the first balanced {...} substring. Tolerates leading/trailing
    prose the model adds despite instructions not to."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _normalize_keys(raw: dict) -> dict:
    out = {}
    for k, v in raw.items():
        canonical = _KEY_ALIASES.get(str(k).lower(), k)
        out[canonical] = v
    return out


def _normalize_evidence_tags(tags: list, task: str) -> tuple[list[str], list[str]]:
    """Returns (canonical_task_evidence_values, unmapped_raw_tags)."""
    if task not in _EVIDENCE_FIELD_BY_TASK:
        return [], [str(t) for t in tags]
    _, allowed = _EVIDENCE_FIELD_BY_TASK[task]
    aliases = _ALIASES_BY_TASK[task]
    canonical, unmapped = [], []
    for raw_tag in tags:
        tag = str(raw_tag).strip()
        key = tag.lower()
        if tag in allowed:
            canonical.append(tag)
            continue
        if key in aliases:
            mapped = aliases[key]
            if mapped is not None:
                canonical.append(mapped)
            else:
                unmapped.append(tag)  # explicitly a non-evidence-field concept; kept for visibility
            continue
        unmapped.append(tag)
    return canonical, unmapped


def parse_qwen_response(raw_text: str, task: str, model_name: str = "") -> tuple[Optional[VisionAnalysis], ParseStatus, dict]:
    """Never raises. Returns (analysis_or_None, status, diagnostics).

    status == "clean" here always -- the caller (qwen7b_vision_analyzer.py)
    is responsible for relabeling a *second, successful* call as "repaired".
    This function only ever reports clean-success or failed for a single
    parse attempt.
    """
    diagnostics: dict[str, Any] = {"raw_preview": (raw_text or "")[:300], "unmapped_tags": []}

    if not raw_text or not raw_text.strip():
        diagnostics["error"] = "empty_response"
        return None, "failed", diagnostics

    candidate = strip_code_fences(raw_text)
    json_str = extract_json_object(candidate)
    if json_str is None:
        diagnostics["error"] = "no_json_object_found"
        return None, "failed", diagnostics

    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError as exc:
        diagnostics["error"] = f"json_decode_error: {exc}"
        return None, "failed", diagnostics

    if not isinstance(obj, dict):
        diagnostics["error"] = "top_level_not_an_object"
        return None, "failed", diagnostics

    obj = _normalize_keys(obj)

    evidence_field, _ = _EVIDENCE_FIELD_BY_TASK.get(task, (None, set()))
    payload: dict[str, Any] = {
        "quality": obj.get("quality") or {"usable": True},
        "scene": obj.get("scene"),
        "objects": obj.get("objects") or [],
        "visible_text": obj.get("visible_text") or [],
        "visual_evidence": list(obj.get("visual_evidence") or []),
        "model_name": str(obj.get("model_name") or model_name or ""),
        "parser_version": PARSER_VERSION,
    }

    positive_tags = obj.get("evidence") or []
    blocker_tags = obj.get("blockers") or []
    if not isinstance(positive_tags, list):
        positive_tags = [positive_tags]
    if not isinstance(blocker_tags, list):
        blocker_tags = [blocker_tags]

    canonical_positive, unmapped_positive = _normalize_evidence_tags(positive_tags, task)
    canonical_blockers, unmapped_blockers = _normalize_evidence_tags(blocker_tags, task)
    diagnostics["unmapped_tags"] = unmapped_positive + unmapped_blockers

    merged_task_evidence: list[str] = []
    if evidence_field:
        merged_task_evidence = sorted(set(canonical_positive) | set(canonical_blockers))
        payload[evidence_field] = merged_task_evidence
    payload["visual_evidence"] = sorted(set(payload["visual_evidence"]) | set(unmapped_positive) | set(unmapped_blockers))
    # raw blocker tags are kept verbatim (not just the canonicalized subset) so the guard sees
    # exactly what the model called a blocker, even if it doesn't map to a task evidence enum.
    payload["blockers"] = sorted(set(str(t) for t in blocker_tags))

    uncertainty = str(obj.get("uncertainty") or "low").lower()
    payload["uncertainty"] = uncertainty if uncertainty in _UNCERTAINTY_VALUES else "high"

    if task == "exercise" and _has_contradictory_exercise_environments(set(merged_task_evidence)):
        payload["uncertainty"] = "high"  # never trust a self-contradictory scene as low-uncertainty
        diagnostics["contradictory_scene_evidence"] = True
        print(f"[qwen_evidence_parser] CONTRADICTORY exercise environment tags in same image: "
              f"{sorted(set(merged_task_evidence))} -- forcing uncertainty=high")

    complexity = str(obj.get("scene_complexity") or "simple").lower()
    payload["scene_complexity"] = complexity if complexity in _SCENE_COMPLEXITY_VALUES else "moderate"

    # objects: keep only well-formed {label, confidence} entries; malformed entries are dropped
    # but recorded in diagnostics rather than crashing validation.
    clean_objects = []
    dropped_objects = []
    for o in payload["objects"]:
        if isinstance(o, dict) and "label" in o:
            clean_objects.append({"label": str(o["label"]), "confidence": float(o.get("confidence") or 0.0)})
        else:
            dropped_objects.append(o)
    payload["objects"] = clean_objects
    if dropped_objects:
        diagnostics["dropped_objects"] = dropped_objects

    quality = payload["quality"]
    if isinstance(quality, dict):
        try:
            payload["quality"] = ImageQuality(**quality)
        except Exception as exc:  # noqa: BLE001
            diagnostics["error"] = f"quality_validation_error: {exc}"
            return None, "failed", diagnostics

    try:
        payload["objects"] = [ImageObjectObservation(**o) for o in payload["objects"]]
        analysis = VisionAnalysis(**payload)
    except Exception as exc:  # noqa: BLE001
        diagnostics["error"] = f"schema_validation_error: {exc}"
        return None, "failed", diagnostics

    return analysis, "clean", diagnostics


def build_repair_prompt(original_raw_text: str, task: str, error: str) -> str:
    """One-shot repair instruction. Used at most once by the caller."""
    field, allowed = _EVIDENCE_FIELD_BY_TASK.get(task, ("evidence", set()))
    allowed_str = ", ".join(sorted(allowed))
    return (
        "Your previous response could not be parsed as valid JSON matching the required schema "
        f"(error: {error}).\n\n"
        f"Previous response:\n{original_raw_text[:1000]}\n\n"
        "Return ONLY a single JSON object (no markdown code fence, no extra text) with exactly "
        "these keys: task (string), evidence (list of strings), blockers (list of strings), "
        "uncertainty (one of: low, medium, high), scene_complexity (one of: simple, moderate, "
        "complex), parser_version (string, echo back what you were given or omit), model_name "
        "(string).\n"
        f"For task=\"{task}\", evidence/blockers entries must be chosen from: {allowed_str}.\n"
        "Do not include verified, rejected, retake_required, result, score, pass, fail, decision, "
        "or judgment anywhere in the response."
    )
