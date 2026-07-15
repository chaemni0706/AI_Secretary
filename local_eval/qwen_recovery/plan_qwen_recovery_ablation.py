#!/usr/bin/env python3
"""Phase 8 skeleton: operationalizes qwen_recovery_ablation_plan.md as a
machine-readable spec and (optionally) scaffolds empty output directories.

Runs NO model inference. Default mode is dry-run: prints what would be
created and exits 0 without touching the filesystem. Pass
--confirm-create-dirs to actually create the (empty) per-ablation output
directory skeleton described in qwen_recovery_ablation_plan.md §2.

Usage:
    python3 plan_qwen_recovery_ablation.py --help
    python3 plan_qwen_recovery_ablation.py                       # dry-run, prints plan
    python3 plan_qwen_recovery_ablation.py --confirm-create-dirs  # creates empty dirs only
"""
import argparse
import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

ABLATIONS = [
    {"id": 1, "name": "qwen_baseline", "branches": [], "guard": False,
     "description": "Single Qwen2.5-VL-7B pass, generic prompt, no crop/OCR/re-question."},
    {"id": 2, "name": "qwen_requestion_only", "branches": ["A_generic_repeat"], "guard": False,
     "description": "Baseline + a second generic-prompt pass on recovery_needed images "
                     "(sampling-variance control)."},
    {"id": 3, "name": "qwen_yolo_crop", "branches": ["A", "B"], "guard": False,
     "description": "Baseline + task-specific prompt + routed YOLO crop on recovery_needed images."},
    {"id": 4, "name": "qwen_ocr", "branches": ["A", "C"], "guard": False,
     "description": "Baseline + OCR-hint prompt, study only, on recovery_needed study images with a doc/screen crop."},
    {"id": 5, "name": "qwen_yolo_crop_ocr", "branches": ["A", "B", "C"], "guard": False,
     "description": "Ablations 3+4 combined."},
    {"id": 6, "name": "qwen_yolo_crop_ocr_hard_guard", "branches": ["A", "B", "C", "F"], "guard": True,
     "description": "Ablation 5 + Branch F merge-then-decide with hard-negative guard candidates enforced."},
    {"id": 7, "name": "smol_blocker_qwen_yolo_crop_ocr_guard", "branches": ["E", "A", "B", "C", "F"], "guard": True,
     "description": "Branch E (live SmolVLM-500M first pass) escalating to ablation 6 only when "
                     "recovery_needed=true. The realistic deployment candidate."},
    {"id": 8, "name": "optional_siglip_guard_only_if_user_approves", "branches": ["E", "A", "B", "C", "D", "F"],
     "guard": True, "requires_separate_approval": True,
     "description": "Ablation 7 + Branch D (SigLIP hard-negative pre-filter). Gated -- not runnable "
                     "without a separate, explicit user approval per qwen_recovery_branch_design.md Branch D."},
]

OUTPUT_FILES = ["predictions.jsonl", "metrics_by_task.csv", "fp_cases.csv", "fn_cases.csv",
                "latency_summary.csv", "report.md"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", default=str(THIS_DIR / "ablation_results"))
    ap.add_argument("--confirm-create-dirs", action="store_true",
                     help="Actually create the empty per-ablation output directories. "
                          "Without this flag, the script only prints the plan (dry-run).")
    ap.add_argument("--json", action="store_true", help="Print the ablation spec as JSON instead of a table.")
    args = ap.parse_args()

    if args.json:
        print(json.dumps(ABLATIONS, indent=2, ensure_ascii=False))
    else:
        print(f"{'id':<3} {'name':<38} {'guard':<6} {'approval?':<10} description")
        for a in ABLATIONS:
            approval = "YES" if a.get("requires_separate_approval") else ""
            print(f"{a['id']:<3} {a['name']:<38} {str(a['guard']):<6} {approval:<10} {a['description']}")

    results_dir = Path(args.results_dir)
    if not args.confirm_create_dirs:
        print(f"\n[dry-run] would create: {results_dir}/<ablation_name>/ "
              f"with empty placeholders for: {', '.join(OUTPUT_FILES)}")
        print("[dry-run] no model inference is run by this script, ever. "
              "Pass --confirm-create-dirs to create the empty directory skeleton "
              "(still no inference, no data).")
        return

    for a in ABLATIONS:
        d = results_dir / a["name"]
        d.mkdir(parents=True, exist_ok=True)
        readme = d / "README.md"
        readme.write_text(
            f"# {a['name']} (ablation #{a['id']})\n\n{a['description']}\n\n"
            f"Not yet run. Expected outputs (per qwen_recovery_ablation_plan.md §2): "
            f"{', '.join(OUTPUT_FILES)}\n",
            encoding="utf-8",
        )
        print(f"created {d}/ (README.md placeholder only, no predictions)")


if __name__ == "__main__":
    main()
