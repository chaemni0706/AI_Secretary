# Baseline Artifact Inventory (full171 / final_manifest.csv basis)

Goal: find every existing baseline result relevant to a Qwen recall-recovery
ablation framework, and state plainly what is and is not reproducible right
now without new inference. Search commands used:
`rg -n "Qwen|qwen|7B|FP=6|recall|0.481|eligible|full171|final171|real_validation_dataset" local_eval reports backend tests scripts`
(this repo has no top-level `reports/`/`scripts/` dirs — searched what exists:
`local_eval`, `backend`, `tests`, plus root `*.md`).

## 1. Three separate baseline artifacts exist — not one

| # | Model | Scope | Per-image data on disk? | Aggregate numbers |
|---|---|---|---|---|
| A | Qwen2.5-VL-7B-Instruct (bf16) + `vlm_fp_guard` | full171, all 3 tasks | **No** — `local_eval/vlm_baseline/outputs/` is gitignored (`.gitignore` line 79) and absent from disk | `VLM_FALLBACK_STABILIZATION_REPORT.md` §4a table only (recall 0.481, FP=6) |
| B | Qwen2.5-VL-3B-AWQ (`qwen_awq` adapter) | 10-image **mini-probe**, study only | Yes — `local_eval/ondevice_vlm_eval/outputs/runs/20260707_011338_qwen_awq_study/{predictions.jsonl,metrics_summary.json,...}` | recall 1.0 (n=10 — too small to trust as a study baseline) |
| C | SmolVLM-500M | **full171, all 3 tasks**, via the real `evaluate_image_verification` Rule Engine | **Yes, complete** — `local_eval/real_validation_dataset/results/smolvlm500_final/` (`predictions.jsonl`, `per_image.csv`, `false_positive_cases.json`, `false_negative_cases.json`, `borderline_cases.json`, `rule_diagnostics.json`, `metrics_summary.json`, dated 2026-07-09) | recall 0.2469, FP=9 (borderline_as_fail) |

Per `vlm_current_pipeline_audit.md`, **C is the model that actually runs by
default** for the live `/image-verifications` and `/verification/image/{type}`
endpoints (all 3 tasks); A is a validated-but-unwired alternative
architecture; B is a fragment too small to use as a baseline on its own.

## 2. What each artifact actually contains

**A — Qwen2.5-VL-7B + guard (`VLM_FALLBACK_STABILIZATION_REPORT.md`)**:
task-level recall/accuracy/FP table (§4a, reproduced in
`vlm_current_pipeline_audit.md` §8), a hand-written 6-row FP breakdown table
(§4a, image_id/GT/reason/character for each of the 6 FP), and a
qualitative eligible-scope re-classification (§3: `non_visual_context_required`
x2, `label_review_needed` x2, `borderline_policy` x2). **No FN list, no
per-image evidence dump, no predictions.jsonl.** The report references
`recompute_metrics_with_scope.py` → `metrics_scope_adjusted.json` and
`fp_scope_review.csv` as its computation trail, but neither output file
exists on disk (script exists at `local_eval/vlm_baseline/recompute_metrics_with_scope.py`,
its output was never committed/is gitignored).

**B — Qwen2.5-VL-3B-AWQ study mini-probe**: full per-image
`predictions.jsonl` and `metrics_summary.json` for exactly 10 study images,
tp=7/tn=3/fp=0/fn=0. Too small (10 of 54 study images) to serve as a study
baseline; useful only as a sanity check that the adapter runs and parses
correctly.

**C — SmolVLM-500M full171** (`local_eval/real_validation_dataset/results/smolvlm500_final/`):
complete, reproducible-without-new-inference artifact set:
- `predictions.jsonl` — full per-image VisionAnalysis + rule result
- `per_image.csv` — `image_id,task,ground_truth,pred_result,verified,score,mandatory_passed,got_evidence,rule_evidence` (171 rows)
- `false_negative_cases.json` (61 entries), `false_positive_cases.json` (9), `borderline_cases.json`
- `rule_diagnostics.json` — result distribution, rule_evidence frequency counts
- `metrics_summary.json`/`.csv` — both `borderline_as_fail` and `borderline_excluded`, per-task and ALL
- `latency_summary.json`, `dataset_hygiene.json`, `evidence_metrics.json`, `safety_summary.json`
- `FP_montage.png` — visual contact sheet of the 9 FP images

This is the artifact `analyze_false_negatives.py` (Phase 3) reads.

## 3. Is a full171 evaluation of the true live default reproducible right now?

**Partially, with a gap.** The live default is "SmolVLM-500M primary for all
3 tasks, PLUS a conditional qwen_awq escalation for study only when the first
pass is weak" (`vlm_current_pipeline_audit.md` §1). Artifact C measures
SmolVLM-500M alone, with **no** qwen_awq study escalation applied (confirmed
by reading `run_smolvlm_final_inference.py`'s header: it calls
`evaluate_image_verification` directly with only the SmolVLM adapter's
evidence, never invoking `verify_image_upload`'s fallback branch). So:
- water/exercise numbers in artifact C **are** representative of the live
  default today (no fallback exists for those tasks regardless).
- study numbers in artifact C are a **lower bound** on the live default —
  the real service would additionally escalate some `retake_required`/
  `rejected` study results to qwen_awq per `_should_study_fallback()`'s
  trigger conditions, which could recover some of the 17 study FN in
  artifact C. No run exists that measures this combined behavior on the
  full 54 study images (artifact B covers only 10).

## 4. To reproduce or extend any of these (not run in this task)

- Re-running A requires the `containers`/model weights this repo's Qwen2.5-VL-7B
  setup depends on (not verified present on this server as part of this
  read-only audit) plus re-executing `local_eval/vlm_baseline/run_vlm_fallback_full_eval.py`
  against the 171-image manifest.
- Filling the study-escalation gap in C requires running
  `verify_image_upload` end-to-end (not just the Rule Engine) with
  `IMAGE_VERIFICATION_STUDY_FALLBACK=qwen_awq` on the 54 study images that
  didn't verify under SmolVLM alone -- a targeted, much smaller inference job
  than a full A-style 171-image run.
- Any new inference of either kind requires explicit user approval per this
  task's Phase 6 instruction; not run here.

## 5. What's missing / cannot be inventoried further without inference

- No FP case list exists for artifact A (only the 6-row markdown table,
  which is sufficient for the regression set in `qwen_fp_guard_regression_set.csv`
  but not for programmatic joins).
- No `eligible_scope` per-image flag file exists — `fp_scope_review.csv`
  (referenced by the stabilization report) is not present on disk.
- No prompt/template file used for the A run was found under `local_eval/vlm_baseline/`
  beyond `prompts.py`'s Python string constants (not a separate YAML/JSON
  template file) -- read for reference, not modified.
