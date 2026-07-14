# Qwen Recall-Recovery — Ablation Plan (design only, not executed)

All 8 combinations below run on the same 171-image manifest
(`local_eval/real_validation_dataset_150_candidate/final_manifest.csv`), the
same real Rule Engine (`evaluate_image_verification`), varying only the
evidence-gathering stage feeding it. **None have been run.** This plan
defines what each combination is, what it must produce, and the success
gate — execution requires explicit user approval (Phase 6 of this task).

## 0. Baseline reference numbers (already measured, not re-derived here)

Two baselines exist and must be reported side by side, per
`qwen_baseline_artifact_inventory.md` — they are not interchangeable:

| | model | scope | recall | FP | reproducible now? |
|---|---|---|---|---|---|
| Real live default | SmolVLM-500M (all 3 tasks, no fallback applied in this specific run) | full171 | 0.2469 | 9 | yes, on disk |
| Validated-but-unwired harness | Qwen2.5-VL-7B + guard | full171 | 0.481 | 6 | no — aggregate only |

Ablation 1 (`qwen_baseline`) below is deliberately named for the second row
(the actual Qwen upgrade path this task is about), understanding it cannot
be scored against on-disk per-image data until it is actually run.

## 1. The 8 combinations

| # | name | evidence stage(s) | guard |
|---|---|---|---|
| 1 | `qwen_baseline` | Single Qwen2.5-VL-7B pass, generic prompt (current `vision_analyzer.py::_build_prompt`), no crop/OCR/re-question | none |
| 2 | `qwen_requestion_only` | (1) + a second Qwen pass with the SAME generic prompt on `recovery_needed=true` images only (sampling-variance control, isolates "does asking twice help" from "does asking better help") | none |
| 3 | `qwen_yolo_crop` | (1) + Branch B: task-specific prompt (`qwen_recovery_prompts.yaml`) + routed YOLO crop, on `recovery_needed=true` images | none |
| 4 | `qwen_ocr` | (1) + Branch C: `study_ocr_recheck` prompt + OCR text hint, study only, on `recovery_needed=true` study images with a doc/screen crop | none |
| 5 | `qwen_yolo_crop_ocr` | (3) + (4) combined | none |
| 6 | `qwen_yolo_crop_ocr_hard_guard` | (5) + Branch F's merge-then-decide step applies `hard_negative_guard_candidates` as an explicit pre-decision check (any hard-negative candidate present blocks `verified` regardless of what the recovery pass found) | reason-keyword guard (mirrors `local_eval/vlm_baseline/vlm_fp_guard.py`'s approach, reimplemented against this pipeline's evidence shape — not a copy-paste, since this pipeline's evidence is structured JSON, not free-text `reason`) |
| 7 | `smol_blocker_qwen_yolo_crop_ocr_guard` | Branch E (SmolVLM-500M first pass, current live default) → only escalate to (6) when SmolVLM's result is `recovery_needed=true` (no hard blocker, weak/no positive evidence) — this is the full proposed production shape | same as 6 |
| 8 | `optional_siglip_guard_only_if_user_approves` | (7) + Branch D (SigLIP hard-negative pre-filter) — **not run without separate, explicit user approval**, per `qwen_recovery_branch_design.md` Branch D | guard 6 + SigLIP pre-filter |

Ablations 1-2 exist to establish how much of any later gain is just
"asking Qwen again" vs. "asking Qwen something more specific." Ablation 7 is
the realistic deployment candidate (reuses the already-live SmolVLM first
pass rather than discarding it). Ablation 8 is explicitly gated.

## 2. Per-ablation outputs

Each ablation, once run, must produce (directory
`local_eval/qwen_recovery/ablation_results/<name>/`, not created yet):

```
predictions.jsonl      # one record per image: image_id, task, gt_label, final_result,
                        #   engine_used, evidence (merged), guard_reason (if any)
metrics_by_task.csv    # schema below
fp_cases.csv           # image_id, task, gt_label, final_result, evidence, guard_reason
fn_cases.csv           # image_id, task, gt_label, final_result, evidence, likely_failure_type
latency_summary.csv    # per-image and aggregate (mean/p50/p95/max) wall-clock ms
report.md              # human-readable summary + comparison to ablation 1 and to
                        #   both baselines in §0
```

## 3. Metric schema (per ablation, per task and ALL, both BORDERLINE modes)

```
task, n, TP, TN, FP, FN, accuracy, precision, recall, f1,
borderline_as_fail, borderline_excluded, eligible_scope_FP, full171_FP
```

- `borderline_as_fail` / `borderline_excluded`: two full metric blocks per
  task (matches this project's and the YOLO project's existing convention).
- `eligible_scope_FP`: FP count after excluding the same
  non-visual/appearance-indistinguishable category documented in
  `VLM_FALLBACK_STABILIZATION_REPORT.md` §3 (image-level exclusion list must
  be carried forward unchanged, not redefined per ablation — redefining it
  per-ablation would be a disguised way to lower the FP bar).
- `full171_FP`: FP count with no exclusions — the primary gate metric.

## 4. Success condition (per ablation, and for selecting a final combination)

- Overall recall >= 0.80 (`borderline_as_fail`, full171).
- `full171_FP` does not exceed the FP of whichever baseline this ablation is
  compared against (ablation 1's own measured FP once run; if ablation 1's
  measured FP differs from the harness's historical FP=6, the newly measured
  number is authoritative for the comparison, not the old report).
- `eligible_scope_FP` == 0 maintained throughout every ablation, not only the
  final one.
- No single task's FP increases versus ablation 1, even if the overall FP
  number looks flat (an increase in one task masked by a decrease in another
  is a regression, not a wash).
- An ablation that raises recall by raising FP in any task is a **failed**
  ablation regardless of its recall number, per this task's absolute
  principle.

## 5. Regression requirement (every ablation, always checked)

Every ablation's `fp_cases.csv` is checked against
`qwen_fp_guard_regression_set.csv` (Phase 9) — every image in that regression
set must still resolve to `rejected`/`retake_required` in every ablation. A
single regression-set image flipping to `verified` in any ablation fails
that ablation outright, independent of its aggregate recall/FP numbers.

## 6. Explicit non-goals

- No ablation may lower `backend/rules/image_verification/*.yaml`'s
  `thresholds.verified`/`thresholds.retake_required` to raise recall.
- No ablation's FP-guard step may be tuned by looking at this same 171-image
  set's FP outcomes and adjusting keyword lists to match — any guard keyword
  list must be justified from the evidence taxonomy (e.g.
  `vlm_fp_guard.py`'s existing `_WATER_NEG`/`_EX_NEG` lists as prior art), not
  fit post-hoc to this dataset's specific FP images.
- Ablation 8 (SigLIP) may not be promoted to the default chain without a
  separate explicit approval step, even if it appears to help in isolation.
