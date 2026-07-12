"""Scope-adjusted metrics: VLM-eligible visual subset 기준 재계산.

배경: full-test residual FP 중 일부는 외관 기반 VLM 으로 판단 불가한 케이스
(변기 물탱크 물/오염 식수 = non_visual_context_required, 옅은 맥주+물 동시 = label_review_needed,
BORDERLINE = borderline_policy). 이들을 VLM-only 자동 확정 대상에서 제외한 **eligible subset** 에서
FP 를 재계산한다. (원본 metrics 는 유지; 이 스크립트는 scope 조정본만 산출.)

사용:
  python recompute_metrics_with_scope.py \
    --predictions outputs/vlm_fallback_full_eval_7bguard/predictions.jsonl \
    --fp-scope   outputs/vlm_fallback_full_eval_7bguard/fp_scope_review.csv \
    --output     outputs/vlm_fallback_full_eval_7bguard/metrics_scope_adjusted.json

fp_scope_review.csv 의 scope_decision 이 out_of_scope 또는 review_required 인 image_id 는
eligible subset 에서 제외한다(=VLM-only 확정 대상 아님). eligible 은 그대로 평가.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

EXCLUDE_DECISIONS = {"out_of_scope", "review_required"}


def _conf(rows):
    tp = sum(1 for x in rows if x["ground_truth"] == "PASS" and x["final_result"] == "verified")
    fp = sum(1 for x in rows if x["ground_truth"] != "PASS" and x["final_result"] == "verified")
    tn = sum(1 for x in rows if x["ground_truth"] != "PASS" and x["final_result"] != "verified")
    fn = sum(1 for x in rows if x["ground_truth"] == "PASS" and x["final_result"] != "verified")
    n = len(rows)
    rec = tp / (tp + fn) if tp + fn else 0
    return dict(n=n, tp=tp, tn=tn, fp=fp, fn=fn, recall=round(rec, 3),
                accuracy=round((tp + tn) / n, 3) if n else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--fp-scope", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    preds = [json.loads(l) for l in Path(args.predictions).read_text(encoding="utf-8").splitlines() if l.strip()]
    scope = {r["image_id"]: r for r in csv.DictReader(Path(args.fp_scope).open(encoding="utf-8-sig"))}
    excluded_ids = {iid for iid, r in scope.items() if r["scope_decision"] in EXCLUDE_DECISIONS}

    # original
    orig_fps = [p for p in preds if p["ground_truth"] != "PASS" and p["final_result"] == "verified"]
    orig_task_fp = {t: sum(1 for p in orig_fps if p["task"] == t) for t in ("water", "study", "exercise")}

    # eligible subset = 전체 - excluded
    eligible = [p for p in preds if p["image_id"] not in excluded_ids]
    excluded = [p for p in preds if p["image_id"] in excluded_ids]
    elig_fps = [p for p in eligible if p["ground_truth"] != "PASS" and p["final_result"] == "verified"]
    elig_task_fp = {t: sum(1 for p in elig_fps if p["task"] == t) for t in ("water", "study", "exercise")}

    # excluded reason counts (from fp_scope categories)
    excl_cat = Counter(scope[i]["fp_category"] for i in excluded_ids if i in scope)

    # safety: verified from engine_error/parse_failed
    v_from_err = sum(1 for p in preds if p["final_result"] == "verified"
                     and (p.get("local_error") or p.get("fallback_error") == "fallback_engine_error"
                          or p.get("local_parse_status") == "failed" or p.get("fallback_parse_status") == "failed"))

    metrics = {"ALL": _conf(eligible)}
    for t in ("water", "study", "exercise"):
        metrics[t] = _conf([p for p in eligible if p["task"] == t])

    result = {
        "original": {
            "n": len(preds), "FP": len(orig_fps), "task_fp": orig_task_fp,
            "decision": "DO_NOT_CONFIRM" if orig_fps else "CONFIRM_OK",
        },
        "scope_adjusted": {
            "eligible_n": len(eligible), "excluded_n": len(excluded),
            "FP": len(elig_fps), "task_fp": elig_task_fp,
            "metrics": metrics,
            "verified_from_error_or_parsefail": v_from_err,
            "decision": ("CONFIRM_ELIGIBLE_SCOPE" if (not elig_fps and v_from_err == 0) else "DO_NOT_CONFIRM"),
        },
        "excluded": {
            "visual_indistinguishable": excl_cat.get("visual_indistinguishable", 0),
            "non_visual_context_required": excl_cat.get("non_visual_context_required", 0),
            "borderline_policy": excl_cat.get("borderline_policy", 0),
            "label_review_needed": excl_cat.get("label_review_needed", 0),
            "visual_model_error": excl_cat.get("visual_model_error", 0),
        },
        "excluded_ids": sorted(excluded_ids),
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
