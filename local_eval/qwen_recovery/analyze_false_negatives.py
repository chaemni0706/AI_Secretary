#!/usr/bin/env python3
"""Phase 3: false-negative analysis for the recovery-ablation framework.

IMPORTANT DATA-PROVENANCE NOTE (read before trusting any number here):
There is no Qwen-specific full171 per-image prediction file on disk in this
repo. `local_eval/vlm_baseline/outputs/` (where the Qwen2.5-VL-7B+guard
harness's per-image results would live) is gitignored and absent from disk --
only its AGGREGATE numbers survive, in VLM_FALLBACK_STABILIZATION_REPORT.md.
The Qwen2.5-VL-3B-AWQ study-only run that does have per-image data
(local_eval/ondevice_vlm_eval/outputs/runs/20260707_011338_qwen_awq_study/)
is a 10-image mini-probe, not the full 54-image study set.

The only full171, per-image, on-disk, reproducible prediction set is
`local_eval/real_validation_dataset/results/smolvlm500_final/` --
**SmolVLM-500M**, run through the real `evaluate_image_verification` Rule
Engine. Per `vlm_current_pipeline_audit.md`, SmolVLM-500M (not Qwen) is
actually the current default model for the live `/image-verifications` and
`/verification/image/{type}` endpoints for all three tasks (water/exercise/
study), with Qwen2.5-VL-3B-AWQ only conditionally added for study. So this
is not a downgrade-substitute for "the real baseline" -- it IS the real
baseline's dominant model, just not literally called "Qwen".

This script reads that real, on-disk data. It fabricates nothing. Every
`likely_failure_type` is a deterministic function of the real `rule_evidence`
codes recorded for that image, never invented per-image.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
DEFAULT_FN_JSON = ROOT / "local_eval/real_validation_dataset/results/smolvlm500_final/false_negative_cases.json"
DEFAULT_MANIFEST = ROOT / "local_eval/real_validation_dataset_150_candidate/final_manifest.csv"
DEFAULT_IMAGES_DIR = ROOT / "local_eval/real_validation_dataset_150_candidate/images"


def classify_water(rule_evidence, got_evidence):
    codes = set(rule_evidence)
    if "water_priority:non_water_beverage" in codes:
        return "colored_vs_clear_confusion"
    if "water_priority:opaque_closed_container" in codes:
        return "reflection_or_occlusion"
    if "water_priority:uncertain_liquid" in codes:
        return "transparent_liquid_uncertain"
    if not got_evidence and "water_pattern_missing" in codes:
        return "transparent_liquid_uncertain"
    if any(e.startswith("water_evidence:") for e in got_evidence) and "water_pattern_missing" in codes:
        return "small_container_or_liquid"
    return "empty_vs_clear_confusion"


def classify_study(rule_evidence, got_evidence):
    codes = set(rule_evidence)
    if codes.intersection({"study_priority:gaming_content", "study_priority:entertainment_video",
                            "study_priority:social_media", "study_priority:shopping_content",
                            "study_priority:non_study_screen"}):
        return "entertainment_vs_study_uncertain"
    if "study_priority:uncertain_screen_content" in codes:
        return "laptop_screen_uncertain"
    if any(e.startswith("study_evidence:") for e in got_evidence):
        return "book_or_note_weak"
    if "study_pattern_missing" in codes and not got_evidence:
        return "document_not_recognized"
    return "text_not_read"


def classify_exercise(rule_evidence, got_evidence):
    codes = set(rule_evidence)
    if "exercise_priority:insufficient_exercise_evidence" in codes and got_evidence:
        return "equipment_missing"
    if any("yoga" in e or "pilates" in e for e in got_evidence):
        return "yoga_mat_or_pilates_context_missing"
    if any(e.startswith("exercise_core_equipment") or e.startswith("exercise_mandatory_match") for e in codes):
        return "equipment_missing"
    if not got_evidence and "exercise_pattern_missing" in codes:
        return "gym_environment_not_recognized"
    return "action_not_recognized"


def recovery_branch(task, failure_type):
    """Maps a failure_type to the recovery branches from qwen_recovery_branch_design.md
    most likely to help. Multiple branches may apply; listed by priority."""
    if task == "water":
        return {
            "transparent_liquid_uncertain": "B,A",
            "small_container_or_liquid": "B,A",
            "colored_vs_clear_confusion": "A",
            "reflection_or_occlusion": "A",
            "empty_vs_clear_confusion": "A",
        }.get(failure_type, "A")
    if task == "study":
        return {
            "document_not_recognized": "B,C",
            "text_not_read": "C,B",
            "book_or_note_weak": "C,A",
            "laptop_screen_uncertain": "C,A",
            "entertainment_vs_study_uncertain": "A",
        }.get(failure_type, "A")
    if task == "exercise":
        return {
            "gym_environment_not_recognized": "A",
            "equipment_missing": "B,A",
            "yoga_mat_or_pilates_context_missing": "A",
            "action_not_recognized": "A",
            "person_only_uncertain": "A",
        }.get(failure_type, "A")
    raise ValueError(task)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fn-json", default=str(DEFAULT_FN_JSON))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    ap.add_argument("--out-csv", default=str(THIS_DIR / "qwen_false_negative_cases.csv"))
    ap.add_argument("--out-md", default=str(THIS_DIR / "qwen_false_negative_analysis.md"))
    args = ap.parse_args()

    with open(args.fn_json, encoding="utf-8") as fh:
        fn_cases = json.load(fh)

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        manifest_rows = {r["image_id"]: r for r in csv.DictReader(fh)}

    classifiers = {"water": classify_water, "study": classify_study, "exercise": classify_exercise}

    rows = []
    for case in fn_cases:
        task = case["task"]
        manifest_row = manifest_rows.get(case["image_id"], {})
        image_path = str(Path(args.images_dir) / manifest_row["filepath"].split("images/", 1)[-1]) \
            if manifest_row.get("filepath") else ""
        got_evidence = case.get("got_evidence") or []
        rule_evidence = case.get("rule_evidence") or []
        failure_type = classifiers[task](rule_evidence, got_evidence)
        rows.append({
            "image_id": case["image_id"],
            "task": task,
            "gt_label": case["ground_truth"],
            "image_path": image_path,
            "model_result": case["pred_result"],
            "model_evidence": ";".join(got_evidence),
            "rule_reject_reason": ";".join(rule_evidence),
            "quality_flags": "" if case.get("mandatory_passed") is not False or got_evidence else "possible_quality_or_extraction_gap",
            "likely_failure_type": failure_type,
            "proposed_recovery_branch": recovery_branch(task, failure_type),
        })

    fieldnames = ["image_id", "task", "gt_label", "image_path", "model_result", "model_evidence",
                  "rule_reject_reason", "quality_flags", "likely_failure_type", "proposed_recovery_branch"]
    with open(args.out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    from collections import Counter
    by_task_type = Counter((r["task"], r["likely_failure_type"]) for r in rows)
    by_task = Counter(r["task"] for r in rows)

    lines = []
    lines.append("# False-Negative Analysis (model=SmolVLM-500M, the real live default -- not Qwen)")
    lines.append("")
    lines.append(f"Source: `{Path(args.fn_json).relative_to(ROOT)}` "
                  f"(real, on-disk, full171 run via the actual `evaluate_image_verification` Rule Engine; "
                  f"dated 2026-07-09). **No Qwen-specific full171 FN case file exists on disk** -- see this "
                  f"script's module docstring and `qwen_baseline_artifact_inventory.md` for why.")
    lines.append("")
    lines.append(f"Total FN: **{len(rows)}** ({by_task['water']} water, {by_task['study']} study, "
                  f"{by_task['exercise']} exercise).")
    lines.append("")
    lines.append("## Failure-type breakdown (derived deterministically from real `rule_evidence` codes)")
    lines.append("")
    lines.append("| task | failure_type | count |")
    lines.append("|---|---|---|")
    for (task, ftype), count in sorted(by_task_type.items(), key=lambda kv: (kv[0][0], -kv[1])):
        lines.append(f"| {task} | {ftype} | {count} |")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- **exercise** (29 FN): dominated by `gym_environment_not_recognized`/`action_not_recognized` "
                  "-- SmolVLM-500M extracted literally zero exercise evidence on most of these (`got_evidence=[]`), "
                  "matching the near-total absence of exercise-diagnostic signal already documented for the "
                  "much stronger YOLO/OIV7 detector in the prior YOLO-project task. This is a scene/action "
                  "understanding gap, not something crop routing alone fixes -- Branch A (better re-question "
                  "prompt) is the primary lever; Branch B (YOLO crop) is listed second only where partial "
                  "equipment evidence already existed.")
    lines.append("- **water** (15 FN): mostly `transparent_liquid_uncertain`/`small_container_or_liquid` -- "
                  "consistent with the container/liquid-state ambiguity problem already identified in "
                  "`~/projects/yolo_auth_20260712/reports/yolo_to_vlm_recovery_design.md`. Branch B (a "
                  "YOLO-routed container crop) is proposed first here specifically because SmolVLM-500M is a "
                  "weak small model that plausibly benefits from a zoomed-in region it wasn't given.")
    lines.append("- **study** (17 FN): mixed -- some have partial study evidence (`book_or_note_weak`) that "
                  "just didn't cross the Rule Engine's 2-evidence verify threshold "
                  "(`_STUDY_MIN_EVIDENCE_FOR_VERIFY=2` in `image_verification_service.py`), others have none "
                  "at all (`document_not_recognized`). Branch C (OCR) is proposed first for the "
                  "no-evidence-at-all cases; Branch B (document/screen crop) supports it.")
    lines.append("")
    lines.append(f"Full per-image table: `{Path(args.out_csv).name}` ({len(rows)} rows).")
    lines.append("")

    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"wrote {len(rows)} FN rows to {args.out_csv}")
    print(f"wrote analysis to {args.out_md}")


if __name__ == "__main__":
    main()
