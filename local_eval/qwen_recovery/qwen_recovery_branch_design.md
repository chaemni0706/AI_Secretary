# Qwen Recall-Recovery — Branch Design

Design only (no inference run). Grounded in `vlm_current_pipeline_audit.md`
(real pipeline shape) and `qwen_false_negative_analysis.md` (real FN failure
types, from the SmolVLM-500M full171 run — the actual live default model).
Every branch below produces **evidence only**; none of them may emit
`verified`/`rejected`/`retake_required` directly. The Rule Engine
(`evaluate_image_verification`) plus, where applicable, a guard layer remain
the only decision makers, per this task's absolute principle.

## Branch A — Task-specific re-question

**Trigger**: baseline result != `verified` AND no hard blocker evidence was
returned (i.e. the first pass genuinely lacks positive evidence, rather than
having found a clear contradiction).

**What it does**: re-runs vision analysis with a task-specific, more
targeted prompt (see `qwen_recovery_prompts.yaml`) instead of the generic
single prompt in `vision_analyzer.py::_build_prompt`. Returns a fresh
`VisionAnalysis`-shaped evidence JSON; no decision.

**Why first-priority for exercise**: the FN analysis shows exercise's 29 FN
are dominated by `gym_environment_not_recognized`/`action_not_recognized`
(29/29 have `got_evidence=[]` or near-empty) — a scene/action-understanding
gap that no crop or OCR assistance can close (confirmed independently by the
YOLO project's own object-detection experiment, which found exercise-relevant
objects in only 1.7% of images). A better-worded, more specific prompt is the
only lever available for this task.

## Branch B — YOLO crop recovery

**Trigger**: `recovery_needed` AND `crop_candidates` non-empty (from the
YOLO project's `reports/yolo_aux_crop_manifest.jsonl`, reused as-is — no
YOLO re-inference here).

**What it does**: supplies the routed crop image(s) alongside the full
image as additional model input:
- water → `water_container` target crop
- study → `study_document`/`study_screen` target crop
- exercise → `exercise_person_or_scene`/`exercise_equipment` target crop

**Explicit rule**: the crop is a region-of-interest hint only. `crop_candidates`
being non-empty (i.e., "YOLO found *something* object-shaped here") must
never be treated as positive evidence by itself — this exact anti-pattern
(YOLO object presence alone → verified) is what caused the standalone YOLO
prototype's FP=13 failure documented in `reports/yolo_aux_standalone_report.md`
in the YOLO project.

**Expected value by task**: highest for water (container localization is a
plausible small-model bottleneck — `small_container_or_liquid`/
`transparent_liquid_uncertain` are the majority water FN types), moderate for
study (supports Branch C), **near-zero for exercise** — YOLO crop candidates
for exercise exist in only ~2/171 images project-wide (documented in the YOLO
project's crop-manifest output), so this branch is listed second-priority at
best for exercise and should not be expected to move that task's recall.

## Branch C — OCR recovery

**Trigger**: task == `study` AND a document/screen crop exists (from Branch B).

**What it does**: runs OCR on the routed crop (the YOLO project already
built and validated this exact step — `scripts/run_yolo_aux_standalone.py`'s
`analyze_study` — reusable read-only reference, not copied verbatim since it
lives in a different repo) and includes the raw extracted text as a **hint**
in the re-question prompt (Branch A's `study_ocr_recheck`, see prompts file).

**Guard rule**: OCR text alone never verifies. Entertainment keywords found
in OCR text (youtube/game/netflix/etc., matching
`study.yaml`'s rejected-content categories:
`gaming_content`/`entertainment_video`/`social_media`/`shopping_content`/
`non_study_screen`) are surfaced as **hard-negative guard candidates**, not
silently dropped.

**Why relevant here**: `document_not_recognized` (3 FN) and `text_not_read`
(11 FN, the largest single study failure-type bucket) together account for
14 of 17 study FN — exactly the cases OCR-assisted re-question targets.

## Branch D — CLIP/SigLIP hard-negative optional branch (NOT in default pipeline)

**Status**: excluded from the default ablation chain per this task's
explicit instruction. Documented for completeness only.

**Rationale for exclusion**: confirmed via `clip_siglip_usage_check.md`
(prior YOLO-project task) that CLIP/SigLIP has zero presence in this repo's
production code, and this repo's own calibration history (YOLO project's
`decision_rules.yaml` SigLIP note: real matches score ~0.14, not a 0-1
softmax scale) shows naive thresholding would be unsafe without a proper
calibration pass. **No threshold for this branch may be adopted without
running it first against the FP guard regression set**
(`qwen_fp_guard_regression_set.csv`) and getting explicit user approval —
this branch exists in the ablation plan (`qwen_recovery_ablation_plan.md`
row 8) strictly as an optional, isolated, opt-in comparison.

## Branch E — Smol blocker-first (preserve current live-adjacent behavior)

**Trigger**: always runs first, structurally (not conditionally).

**What it does**: keeps SmolVLM-500M as the first pass for every task — this
matches what the live backend already does by default
(`vlm_current_pipeline_audit.md` §1) and is NOT a new component. The only
change proposed here is disciplined interpretation of its output: SmolVLM
`retake_required`/`rejected` with a genuine hard-blocker code (e.g.
`water_priority:empty_container`, `study_priority:gaming_content`,
`exercise_priority:unrelated_environment`) should short-circuit — no
recovery branch runs, the blocker stands. SmolVLM output with *no* blocker
and *insufficient* positive evidence is exactly the `recovery_needed` trigger
condition for Branches A-C.

**Explicit rule preserved from the real Rule Engine**: SmolVLM (or any
branch's VLM call) never produces `verified` on its own — every path still
terminates in `evaluate_image_verification`.

## Branch F — Evidence merge + Rule Engine (final stage, always runs)

**What it does**: merges evidence from whichever branches actually ran
(baseline SmolVLM pass + any of A/B/C) into one `VisionAnalysis`-shaped
object before the final Rule Engine call:
- Positive evidence lists are unioned.
- **Any contradictory blocker evidence from ANY branch blocks verification**
  — a later branch finding a positive does not erase an earlier branch's
  blocker. This mirrors `_priority_result()`'s existing precedence in
  `image_verification_rule_engine.py`, which this merge step must not
  bypass.
- The merged evidence is passed through the unmodified
  `evaluate_image_verification(...)`, and then — for water/exercise, per
  Branch D's future-guard slot, or immediately once a guard equivalent to
  `local_eval/vlm_baseline/vlm_fp_guard.py` is adopted for this pipeline —
  through a reason-keyword FP guard before the result is returned as final.

**Why this branch is mandatory, not optional**: without it, adding Branches
A-C independently would each be a separate uncontrolled call site into the
Rule Engine, risking exactly the "multiple opportunities to accidentally
verify" failure mode this task's principles forbid. One merge-then-decide
choke point keeps the "Rule Engine + guard decides, always" invariant
enforceable in one place.
