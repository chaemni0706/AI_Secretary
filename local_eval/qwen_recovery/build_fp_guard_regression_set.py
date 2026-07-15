#!/usr/bin/env python3
"""Phase 9: assemble the FP-guard regression set from every real, already-
measured hard/risky case this project has on disk. Fabricates nothing --
every row traces to a specific source file (or, for the Qwen2.5-VL-7B FP=6,
to the specific named images in VLM_FALLBACK_STABILIZATION_REPORT.md, since
no per-image file for that harness survives on disk -- see
qwen_baseline_artifact_inventory.md §2).

wake_up dark/sleeping/empty-room cases: NOT included. No image dataset or
fixture pack for the wake_up VLM verification task was found anywhere in
this repo (only tests/test_wakeup_verification_service.py, which covers the
unrelated session/time-based `wakeup` flow, not the VLM-based `wake_up`
image task). This is stated here rather than silently omitted.
"""
import argparse
import csv
import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
DEFAULT_MANIFEST = ROOT / "local_eval/real_validation_dataset_150_candidate/final_manifest.csv"
DEFAULT_IMAGES_DIR = ROOT / "local_eval/real_validation_dataset_150_candidate/images"
YOLO_ROOT = Path.home() / "projects/yolo_auth_20260712"

# Transcribed directly from VLM_FALLBACK_STABILIZATION_REPORT.md §4 (the only
# surviving record of these 6 images; no per-image file exists on disk).
QWEN_7B_FP6 = [
    {"image_id": "intake_012", "risk_type": "non_visual_context_required",
     "why_dangerous": "Toilet tank water -- appearance is genuinely water; FAIL reason is non-visual (source), unsolvable by any VLM on appearance alone."},
    {"image_id": "water_016", "risk_type": "non_visual_context_required",
     "why_dangerous": "Contaminated tap water -- appearance is genuinely water; FAIL reason is water-quality, not visual."},
    {"image_id": "water_042", "risk_type": "label_review_needed",
     "why_dangerous": "Pale beer perceived as colorless/water-like; a real water glass is also in frame, making the GT=FAIL label itself ambiguous."},
    {"image_id": "water_043", "risk_type": "label_review_needed",
     "why_dangerous": "Same beer-appears-colorless issue as water_042."},
    {"image_id": "water_024", "risk_type": "borderline_policy",
     "why_dangerous": "BORDERLINE label, visually indistinguishable from real water -- a labeling-policy edge case, not a model defect."},
    {"image_id": "water_045", "risk_type": "borderline_policy",
     "why_dangerous": "Same as water_024."},
]


def load_manifest(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["image_id"]: r for r in csv.DictReader(fh)}


def image_path_for(manifest_row, images_dir):
    if not manifest_row:
        return ""
    rel = manifest_row["filepath"].split("images/", 1)[-1]
    return str(images_dir / rel)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    ap.add_argument("--smolvlm-fp-json",
                     default=str(ROOT / "local_eval/real_validation_dataset/results/smolvlm500_final/false_positive_cases.json"))
    ap.add_argument("--yolo-fail-risk-csv", default=str(YOLO_ROOT / "reports/yolo_positive_fail_risk_cases.csv"))
    ap.add_argument("--yolo-standalone-jsonl", default=str(YOLO_ROOT / "reports/yolo_aux_standalone_predictions.jsonl"))
    ap.add_argument("--output", default=str(THIS_DIR / "qwen_fp_guard_regression_set.csv"))
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    images_dir = Path(args.images_dir)
    rows = []
    seen = set()

    def add(image_id, task, risk_type, source, required_blocker, why_dangerous):
        key = (image_id, risk_type)
        if key in seen:
            return
        seen.add(key)
        m = manifest.get(image_id, {})
        rows.append({
            "image_id": image_id,
            "task": task or m.get("task", ""),
            "gt_label": m.get("ground_truth", ""),
            "image_path": image_path_for(m, images_dir),
            "risk_type": risk_type,
            "source": source,
            "required_blocker": required_blocker,
            "why_dangerous": why_dangerous,
        })

    # 1. Qwen2.5-VL-7B+guard full171 FP=6 (transcribed from the stabilization report)
    for item in QWEN_7B_FP6:
        add(item["image_id"], "water", item["risk_type"],
            "VLM_FALLBACK_STABILIZATION_REPORT.md §4 (no per-image file on disk)",
            "empty_container/non_water_beverage/uncertain_liquid (appearance-only ceiling; see why_dangerous)",
            item["why_dangerous"])

    # 2. Real SmolVLM-500M full171 FP=9 (on-disk, reproducible)
    if Path(args.smolvlm_fp_json).is_file():
        with open(args.smolvlm_fp_json, encoding="utf-8") as fh:
            for c in json.load(fh):
                add(c["image_id"], c["task"], "smolvlm500_measured_fp",
                    "local_eval/real_validation_dataset/results/smolvlm500_final/false_positive_cases.json",
                    ";".join(c.get("rule_evidence", [])),
                    f"SmolVLM-500M (the real live default model) verified this FAIL/BORDERLINE image on "
                    f"{args.manifest and manifest.get(c['image_id'], {}).get('ground_truth', '')} ground truth.")

    # 3. YOLO positive fail-risk cases (cross-repo, read-only, retired YOLO project)
    if Path(args.yolo_fail_risk_csv).is_file():
        with open(args.yolo_fail_risk_csv, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                add(r["image_id"], r["task"], "yolo_positive_fail_risk",
                    "yolo_auth_20260712/reports/yolo_positive_fail_risk_cases.csv",
                    r.get("detected_relevant_classes", ""),
                    "A YOLO-relevant object was detected on a FAIL/BORDERLINE image; any crop-assisted "
                    "recovery branch must not let this become a false verify.")

    # 4. YOLO standalone reason-coded risk cases (study entertainment/laptop-only, exercise sofa/rest/person-only)
    if Path(args.yolo_standalone_jsonl).is_file():
        target_reasons = {
            "entertainment_context_detected": "study",
            "weak_laptop_only_insufficient": "study",
            "stationary_contradiction_context_detected": "exercise",
            "person_only_insufficient": "exercise",
        }
        with open(args.yolo_standalone_jsonl, encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                if rec["reason"] in target_reasons and rec["gt_label"] != "PASS":
                    add(rec["image_id"], rec["task"], f"yolo_standalone:{rec['reason']}",
                        "yolo_auth_20260712/reports/yolo_aux_standalone_predictions.jsonl",
                        rec["reason"],
                        f"YOLO-project standalone prototype's rule reason was '{rec['reason']}' on a "
                        f"{rec['gt_label']} image -- this exact reason code must keep resolving to "
                        f"rejected/retake_required.")

    # 5. wake_up dark/sleeping/empty-room -- explicitly not available (see module docstring)

    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        fieldnames = ["image_id", "task", "gt_label", "image_path", "risk_type", "source",
                      "required_blocker", "why_dangerous"]
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"wrote {len(rows)} regression rows to {args.output}")
    print("wake_up dark/sleeping/empty-room cases: NOT included (no dataset found).")


if __name__ == "__main__":
    main()
