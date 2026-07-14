# False-Negative Analysis (model=SmolVLM-500M, the real live default -- not Qwen)

Source: `local_eval/real_validation_dataset/results/smolvlm500_final/false_negative_cases.json` (real, on-disk, full171 run via the actual `evaluate_image_verification` Rule Engine; dated 2026-07-09). **No Qwen-specific full171 FN case file exists on disk** -- see this script's module docstring and `qwen_baseline_artifact_inventory.md` for why.

Total FN: **61** (15 water, 17 study, 29 exercise).

## Failure-type breakdown (derived deterministically from real `rule_evidence` codes)

| task | failure_type | count |
|---|---|---|
| exercise | gym_environment_not_recognized | 20 |
| exercise | equipment_missing | 9 |
| study | text_not_read | 11 |
| study | document_not_recognized | 3 |
| study | laptop_screen_uncertain | 3 |
| water | transparent_liquid_uncertain | 15 |

## Interpretation

- **exercise** (29 FN): dominated by `gym_environment_not_recognized`/`action_not_recognized` -- SmolVLM-500M extracted literally zero exercise evidence on most of these (`got_evidence=[]`), matching the near-total absence of exercise-diagnostic signal already documented for the much stronger YOLO/OIV7 detector in the prior YOLO-project task. This is a scene/action understanding gap, not something crop routing alone fixes -- Branch A (better re-question prompt) is the primary lever; Branch B (YOLO crop) is listed second only where partial equipment evidence already existed.
- **water** (15 FN): mostly `transparent_liquid_uncertain`/`small_container_or_liquid` -- consistent with the container/liquid-state ambiguity problem already identified in `~/projects/yolo_auth_20260712/reports/yolo_to_vlm_recovery_design.md`. Branch B (a YOLO-routed container crop) is proposed first here specifically because SmolVLM-500M is a weak small model that plausibly benefits from a zoomed-in region it wasn't given.
- **study** (17 FN): mixed -- some have partial study evidence (`book_or_note_weak`) that just didn't cross the Rule Engine's 2-evidence verify threshold (`_STUDY_MIN_EVIDENCE_FOR_VERIFY=2` in `image_verification_service.py`), others have none at all (`document_not_recognized`). Branch C (OCR) is proposed first for the no-evidence-at-all cases; Branch B (document/screen crop) supports it.

Full per-image table: `qwen_false_negative_cases.csv` (61 rows).

