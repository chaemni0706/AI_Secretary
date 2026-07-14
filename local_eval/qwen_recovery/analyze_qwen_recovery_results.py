#!/usr/bin/env python3
"""Phase 8 skeleton: scores an ablation's predictions.jsonl against
final_manifest.csv ground truth, per the metric schema in
qwen_recovery_ablation_plan.md §3.

Expected predictions.jsonl schema (one JSON object per line):
    {"image_id": str, "task": "water"|"study"|"exercise", "final_result":
     "verified"|"rejected"|"retake_required", "evidence": <any>,
     "guard_reason": str (optional), "engine_used": str (optional)}

This script performs NO model inference -- it only scores an already-produced
predictions file. It does not fabricate one. Run with --help for usage; run
against a real predictions.jsonl once an ablation has actually executed
(none have, per this task's Phase 6 instruction not to run bulk Qwen
inference without approval).
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
DEFAULT_MANIFEST = ROOT / "local_eval/real_validation_dataset_150_candidate/final_manifest.csv"


def confusion(records, borderline_mode):
    if borderline_mode == "excluded":
        records = [r for r in records if r["gt_label"] != "BORDERLINE"]
    tp = tn = fp = fn = 0
    for r in records:
        actual_positive = r["gt_label"] == "PASS"
        predicted_positive = r["final_result"] == "verified"
        if actual_positive and predicted_positive:
            tp += 1
        elif actual_positive and not predicted_positive:
            fn += 1
        elif not actual_positive and predicted_positive:
            fp += 1
        else:
            tn += 1
    n = len(records)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    accuracy = (tp + tn) / n if n else None
    f1 = None
    if precision is not None and recall is not None:
        f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return {"n": n, "TP": tp, "TN": tn, "FP": fp, "FN": fn,
            "accuracy": round(accuracy, 4) if accuracy is not None else "",
            "precision": round(precision, 4) if precision is not None else "",
            "recall": round(recall, 4) if recall is not None else "",
            "f1": round(f1, 4) if f1 is not None else ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", required=True, help="Path to an ablation's predictions.jsonl")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out-dir", required=True, help="Directory to write metrics_by_task.csv/fp_cases.csv/fn_cases.csv/report.md")
    ap.add_argument("--label", default="unnamed_ablation", help="Ablation name, used in report.md")
    args = ap.parse_args()

    with open(args.manifest, newline="", encoding="utf-8") as fh:
        manifest = {r["image_id"]: r for r in csv.DictReader(fh)}

    records = []
    with open(args.predictions, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            rec["gt_label"] = manifest[rec["image_id"]]["ground_truth"]
            records.append(rec)

    if len(records) != 171:
        print(f"WARNING: predictions file has {len(records)} rows, expected 171 (final171 basis). "
              f"Proceeding, but this is not a full171 evaluation.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_task = defaultdict(list)
    for r in records:
        by_task[r["task"]].append(r)

    fieldnames = ["scope", "task", "borderline_handling", "n", "TP", "TN", "FP", "FN",
                  "accuracy", "precision", "recall", "f1"]
    rows = []
    for mode in ("borderline_as_fail", "excluded"):
        row = {"scope": "overall", "task": "ALL", "borderline_handling": mode}
        row.update(confusion(records, mode))
        rows.append(row)
        for task in sorted(by_task):
            row = {"scope": "task", "task": task, "borderline_handling": mode}
            row.update(confusion(by_task[task], mode))
            rows.append(row)

    with open(out_dir / "metrics_by_task.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    fp_rows = [r for r in records if r["gt_label"] != "PASS" and r["final_result"] == "verified"]
    fn_rows = [r for r in records if r["gt_label"] == "PASS" and r["final_result"] != "verified"]

    for name, subset in (("fp_cases.csv", fp_rows), ("fn_cases.csv", fn_rows)):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as fh:
            fields = ["image_id", "task", "gt_label", "final_result", "guard_reason", "evidence"]
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for r in subset:
                w.writerow({
                    "image_id": r["image_id"], "task": r["task"], "gt_label": r["gt_label"],
                    "final_result": r["final_result"], "guard_reason": r.get("guard_reason", ""),
                    "evidence": json.dumps(r.get("evidence", "")),
                })

    overall_primary = next(r for r in rows if r["scope"] == "overall" and r["borderline_handling"] == "borderline_as_fail")
    lines = [f"# {args.label} — results", "",
             f"n={overall_primary['n']}, recall={overall_primary['recall']}, "
             f"FP={overall_primary['FP']}, precision={overall_primary['precision']}",
             "", f"FP cases: {len(fp_rows)} (see fp_cases.csv)",
             f"FN cases: {len(fn_rows)} (see fn_cases.csv)", ""]
    with open(out_dir / "report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"scored {len(records)} records -> {out_dir}")
    print(f"overall (borderline_as_fail): {overall_primary}")


if __name__ == "__main__":
    main()
