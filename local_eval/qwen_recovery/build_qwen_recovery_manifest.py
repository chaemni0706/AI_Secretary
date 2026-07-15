#!/usr/bin/env python3
"""Phase 6: build the input manifest for the recovery-ablation framework.

Does NOT call any model. Assembles, per image:
  - the real baseline result (SmolVLM-500M full171 run -- the actual live
    default model per vlm_current_pipeline_audit.md; NOT a Qwen result,
    since no Qwen full171 per-image file exists on disk -- see
    qwen_baseline_artifact_inventory.md)
  - YOLO crop/OCR/risk evidence, reused read-only from the (now-retired,
    per this task's opening statement) yolo_auth_20260712 project's own
    output reports -- a sibling project directory on this same server, not
    part of this repo, referenced by absolute path and never modified.
  - a deterministic recovery_needed decision (see --help / _recovery_decision).

Usage:
    python3 build_qwen_recovery_manifest.py --help
"""
import argparse
import csv
import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]

DEFAULT_MANIFEST = ROOT / "local_eval/real_validation_dataset_150_candidate/final_manifest.csv"
DEFAULT_BASELINE_PER_IMAGE = ROOT / "local_eval/real_validation_dataset/results/smolvlm500_final/per_image.csv"
DEFAULT_YOLO_CROPS = Path.home() / "projects/yolo_auth_20260712/reports/yolo_aux_crop_manifest.jsonl"
DEFAULT_YOLO_STANDALONE = Path.home() / "projects/yolo_auth_20260712/reports/yolo_aux_standalone_predictions.jsonl"

_HARD_BLOCKER_CODES = {
    "water": {"water_priority:empty_container", "water_priority:non_water_beverage"},
    "study": {"study_priority:gaming_content", "study_priority:entertainment_video",
              "study_priority:social_media", "study_priority:shopping_content",
              "study_priority:non_study_screen"},
    "exercise": {"exercise_priority:unrelated_environment", "exercise_priority:wrong_activity_environment"},
}


def load_jsonl(path):
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as fh:
        return {json.loads(line)["image_id"]: json.loads(line) for line in fh}


def recovery_decision(task, baseline_result, rule_reason_codes, got_evidence):
    """Deterministic trigger, per this task's explicit spec:
      - baseline_result != verified
      - gt_label is NEVER read here (kept out of this function's signature entirely)
      - a clear hard blocker -> no recovery (the blocker stands)
      - quality_unusable -> no recovery (retake is already correct, re-questioning a
        bad photo wastes a model call and cannot fix image quality)
      - no hard blocker + weak/uncertain/missing positive evidence -> recovery
    """
    if baseline_result == "verified":
        return False, "already_verified"
    if "quality_unusable" in rule_reason_codes:
        return False, "quality_unusable_no_recovery_value"
    hard = _HARD_BLOCKER_CODES[task]
    if rule_reason_codes.intersection(hard):
        return False, f"hard_blocker_present:{sorted(rule_reason_codes.intersection(hard))}"
    return True, "no_hard_blocker_and_weak_or_missing_positive_evidence"


def qwen_prompt_types(task, has_doc_or_screen_crop):
    if task == "water":
        return ["water_container_recheck"]
    if task == "study":
        types = ["study_material_recheck"]
        if has_doc_or_screen_crop:
            types.append("study_ocr_recheck")
        return types
    if task == "exercise":
        return ["exercise_scene_recheck"]
    raise ValueError(task)


def recovery_branches(task, crop_candidates):
    """A always available; B only if a crop exists; C only for study with a doc/screen crop."""
    branches = ["A"]
    if crop_candidates:
        branches.append("B")
    if task == "study" and any(c.get("target") in ("study_document", "study_screen") for c in crop_candidates):
        branches.append("C")
    return branches


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--baseline-per-image", default=str(DEFAULT_BASELINE_PER_IMAGE),
                     help="SmolVLM-500M full171 per_image.csv (the real, reproducible baseline).")
    ap.add_argument("--yolo-crops", default=str(DEFAULT_YOLO_CROPS),
                     help="Cross-repo, read-only reference to the retired YOLO project's crop manifest. "
                          "If missing, crop_candidates will be empty for every image (Branch B unavailable).")
    ap.add_argument("--yolo-standalone", default=str(DEFAULT_YOLO_STANDALONE),
                     help="Cross-repo, read-only reference for OCR text hints (study task only).")
    ap.add_argument("--output", default=str(THIS_DIR / "qwen_recovery_manifest.jsonl"))
    args = ap.parse_args()

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        manifest_rows = {r["image_id"]: r for r in csv.DictReader(fh)}
    assert len(manifest_rows) == 171, f"expected 171 manifest rows, found {len(manifest_rows)}"

    with open(args.baseline_per_image, newline="", encoding="utf-8") as fh:
        baseline_rows = {r["image_id"]: r for r in csv.DictReader(fh)}
    assert len(baseline_rows) == 171, f"expected 171 baseline rows, found {len(baseline_rows)}"

    yolo_crops = load_jsonl(Path(args.yolo_crops))
    yolo_standalone = load_jsonl(Path(args.yolo_standalone))
    yolo_available = bool(yolo_crops)

    n_recovery = 0
    with open(args.output, "w", encoding="utf-8") as out_fh:
        for image_id, manifest_row in manifest_rows.items():
            task = manifest_row["task"]
            gt_label = manifest_row["ground_truth"]
            baseline = baseline_rows[image_id]

            got_evidence = [e for e in (baseline.get("got_evidence") or "").split(";") if e]
            rule_reason_codes = set(c for c in (baseline.get("rule_evidence") or "").split(";") if c)
            baseline_result = baseline["pred_result"]

            needed, reason = recovery_decision(task, baseline_result, rule_reason_codes, got_evidence)
            if needed:
                n_recovery += 1

            crop_rec = yolo_crops.get(image_id, {})
            crop_candidates = crop_rec.get("crop_candidates", [])
            risk_flags = crop_rec.get("risk_flags", [])

            standalone_rec = yolo_standalone.get(image_id, {})
            ocr_text = ""
            if task == "study" and standalone_rec:
                ocr_text = standalone_rec.get("aux_evidence", {}).get("ocr_text_preview", "")

            hard_negative_candidates = list(risk_flags)
            if standalone_rec:
                for item in standalone_rec.get("blocker_evidence", []):
                    flag = f"yolo_aux_standalone:{item}"
                    if flag not in hard_negative_candidates:
                        hard_negative_candidates.append(flag)

            record = {
                "image_id": image_id,
                "task": task,
                "gt_label": gt_label,
                "image_path": manifest_row["filepath"],
                "baseline_result": baseline_result,
                "baseline_evidence": got_evidence,
                "baseline_rule_reason": sorted(rule_reason_codes),
                "recovery_needed": needed,
                "recovery_reason": reason,
                "recovery_branches": recovery_branches(task, crop_candidates) if needed else [],
                "crop_candidates": crop_candidates,
                "ocr_text_if_available": ocr_text,
                "yolo_risk_flags": risk_flags,
                "hard_negative_guard_candidates": hard_negative_candidates,
                "prompt_type": qwen_prompt_types(task, any(
                    c.get("target") in ("study_document", "study_screen") for c in crop_candidates
                )) if needed else [],
                "expected_output_schema": "see qwen_recovery_prompts.yaml:expected_output_schema",
            }
            out_fh.write(json.dumps(record) + "\n")

    print(f"wrote {len(manifest_rows)} records to {args.output}")
    print(f"recovery_needed=True count: {n_recovery}")
    if not yolo_available:
        print("WARNING: YOLO crop manifest not found at", args.yolo_crops,
              "-- crop_candidates empty for all images, Branch B/C unavailable in this manifest.")


if __name__ == "__main__":
    main()
