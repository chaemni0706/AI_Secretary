"""고급 성능지표 평가기 (final_manifest + SmolVLM predictions → 인증 시스템 지표).

원칙: VLM raw output 으로 PASS/FAIL 을 만들지 않는다. **Rule Engine 결과(verified/rejected/retake_required)**
기준으로 판정한다(predictions 에 담긴 pred_result). 기존 evaluate_validation_dataset.py 는 건드리지 않는 신규 파일.

입력:
  --manifest    final_manifest.csv 또는 .json (include=Y, ground_truth 확정본)
  --predictions predictions.jsonl 또는 per_image.csv (이미지별 Rule Engine 결과/evidence/latency)
  --run-name    결과 폴더명
  --output-dir  기본 local_eval/real_validation_dataset/results

절대 필터(평가 대상에서 제외): include_in_eval!=Y / ground_truth∉{PASS,FAIL,BORDERLINE}
  / source==synthetic / filepath·notes에 generated|synth|ai-created / exclude_reason 존재.

positive=PASS, pred positive=(Rule Engine result==verified). BORDERLINE 은 두 모드로 산출:
  borderline_as_fail(부정 취급) / borderline_excluded(제외).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
CAND_DIR = THIS_DIR.parent / "real_validation_dataset_150_candidate"
CONTAM = ("generated", "synth", "synthetic", "ai-created", "ai_created")
GTS = {"PASS", "FAIL", "BORDERLINE"}
LAT_KEYS = ["model_load_time", "inference_time", "parse_time", "rule_engine_time",
            "total_time", "latency_ms"]


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _load_predictions(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if path.suffix.lower() == ".json":
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else d.get("results", [])
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _key(r: dict) -> str:
    for k in ("image_id", "image", "filepath", "file"):
        v = r.get(k)
        if v:
            return Path(str(v)).name if k in ("image", "filepath", "file") else str(v)
    return ""


def _aslist(v):
    if isinstance(v, list):
        return [str(x) for x in v if x != ""]
    if v in (None, ""):
        return []
    return [x for x in str(v).replace("|", ";").split(";") if x]


def _is_eval_row(m: dict) -> tuple[bool, str]:
    if str(m.get("include_in_eval", "Y")).upper() != "Y":
        return False, "include!=Y"
    gt = str(m.get("ground_truth", "")).upper()
    if gt not in GTS:
        return False, "gt_not_final"
    if str(m.get("source_type", m.get("source", ""))).lower() == "synthetic":
        return False, "synthetic"
    if str(m.get("exclude_reason", "")).strip():
        return False, "exclude_reason"
    blob = (str(m.get("filepath", "")) + str(m.get("notes", "")) + str(m.get("image_id", ""))).lower()
    if any(t in blob for t in CONTAM):
        return False, "contamination"
    return True, ""


def _confusion(pairs):
    """pairs: (gt_is_pass, pred_is_verified). positive=PASS/verified."""
    tp = sum(1 for g, p in pairs if g and p)
    fp = sum(1 for g, p in pairs if (not g) and p)
    tn = sum(1 for g, p in pairs if (not g) and (not p))
    fn = sum(1 for g, p in pairs if g and (not p))
    n = len(pairs)
    def d(a, b): return round(a / b, 4) if b else 0.0
    return {"n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy": d(tp + tn, n), "precision": d(tp, tp + fp), "recall": d(tp, tp + fn),
            "f1": d(2 * tp, 2 * tp + fp + fn), "false_positive_rate": d(fp, fp + tn),
            "false_negative_rate": d(fn, fn + tp), "specificity": d(tn, tn + fp),
            "negative_predictive_value": d(tn, tn + fn)}


def _pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals); k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return round(s[k], 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--output-dir", default=str(THIS_DIR / "results"))
    ap.add_argument("--borderline", default="both", choices=["both", "as_fail", "excluded"])
    args = ap.parse_args()

    man = _load_rows(Path(args.manifest))
    preds = {_key(p): p for p in _load_predictions(Path(args.predictions))}
    out = Path(args.output_dir) / args.run_name
    out.mkdir(parents=True, exist_ok=True)

    rows, excluded_rows = [], Counter()
    hygiene_contam, missing_pred = [], []
    seen_name, seen_hash, dup = set(), set(), 0

    for m in man:
        ok, why = _is_eval_row(m)
        if not ok:
            excluded_rows[why] += 1
            if why == "contamination":
                hygiene_contam.append(m.get("image_id", "?"))
            continue
        name = Path(m.get("filepath", "")).name
        if name in seen_name:
            dup += 1; excluded_rows["dup_filename"] += 1; continue
        seen_name.add(name)
        k = m.get("image_id") or name
        p = preds.get(k) or preds.get(name)
        if not p:
            missing_pred.append(k); excluded_rows["no_prediction"] += 1; continue
        gt = str(m.get("ground_truth", "")).upper()
        pred_result = str(p.get("pred_result", p.get("result", ""))).lower()
        rows.append({
            "image_id": k, "task": m.get("task"), "ground_truth": gt,
            "pred_result": pred_result, "verified": pred_result == "verified",
            "score": _num(p.get("score")), "mandatory_passed": str(p.get("mandatory_passed")).lower() == "true",
            "got_evidence": _aslist(p.get("got_evidence")),
            "expected_evidence": _aslist(m.get("expected_evidence")),
            "rule_evidence": _aslist(p.get("rule_evidence")),
            "lat": {kk: _num(p.get(kk)) for kk in LAT_KEYS if p.get(kk) not in (None, "")},
        })

    # ---------- 1. task-level + 2. safety (borderline modes) ----------
    def build(mode):
        sub = [r for r in rows if not (mode == "excluded" and r["ground_truth"] == "BORDERLINE")]
        # gt_is_pass: PASS=positive; FAIL/BORDERLINE=negative (as_fail 는 BORDERLINE 도 negative)
        pairs_all, by_task = [], defaultdict(list)
        for r in sub:
            g = r["ground_truth"] == "PASS"
            pairs_all.append((g, r["verified"])); by_task[r["task"]].append((g, r["verified"]))
        return {"ALL": _confusion(pairs_all), **{t: _confusion(v) for t, v in by_task.items()}}, sub

    metrics = {}
    modes = ["as_fail", "excluded"] if args.borderline == "both" else [args.borderline]
    subs = {}
    for mode in modes:
        metrics[f"borderline_{mode}"], subs[mode] = build(mode)

    primary_mode = "as_fail" if "as_fail" in subs else modes[0]
    primary = subs[primary_mode]
    fps = [r for r in primary if (r["ground_truth"] != "PASS") and r["verified"]]
    fns = [r for r in primary if (r["ground_truth"] == "PASS") and (not r["verified"])]
    borderline_cases = [r for r in rows if r["ground_truth"] == "BORDERLINE"]

    safety = {
        "positive_definition": "ground_truth==PASS ; pred positive = RuleEngine verified",
        "borderline_mode_for_safety": primary_mode,
        "FP_count": len(fps),
        "verified_on_fail_count": sum(1 for r in fps if r["ground_truth"] == "FAIL"),
        "fail_open_rate": round(len(fps) / max(1, sum(1 for r in primary if r["ground_truth"] != "PASS")), 4),
        "FP_by_task": dict(Counter(r["task"] for r in fps)),
        "FP_by_rule_evidence": dict(Counter(c for r in fps for c in r["rule_evidence"])),
        "FP_by_evidence_code": dict(Counter(c for r in fps for c in r["got_evidence"])),
        "borderline_as_fail_FP": (metrics.get("borderline_as_fail", {}).get("ALL", {}) or {}).get("fp"),
        "borderline_excluded_FP": (metrics.get("borderline_excluded", {}).get("ALL", {}) or {}).get("fp"),
    }

    # ---------- 3. rule diagnostics ----------
    rule_diag = {
        "result_distribution": dict(Counter(r["pred_result"] for r in rows)),
        "verified_count": sum(1 for r in rows if r["pred_result"] == "verified"),
        "rejected_count": sum(1 for r in rows if r["pred_result"] == "rejected"),
        "retake_required_count": sum(1 for r in rows if r["pred_result"] == "retake_required"),
        "mandatory_passed_rate": round(sum(1 for r in rows if r["mandatory_passed"]) / max(1, len(rows)), 4),
        "score_distribution": _score_hist([r["score"] for r in rows if r["score"] is not None]),
        "rule_evidence_frequency": dict(Counter(c for r in rows for c in r["rule_evidence"]).most_common(40)),
        "rejection_reason_distribution": dict(Counter(
            c for r in rows if r["pred_result"] != "verified" for c in r["rule_evidence"]).most_common(40)),
    }

    # ---------- 4. evidence metrics ----------
    have_expected = any(r["expected_evidence"] for r in rows)
    if have_expected:
        etp = efp = efn = 0; missing_exp = []
        for r in rows:
            exp, got = set(r["expected_evidence"]), set(r["got_evidence"])
            etp += len(exp & got); efp += len(got - exp); efn += len(exp - got)
            if exp - got:
                missing_exp.append({"image_id": r["image_id"], "missing": sorted(exp - got)})
        def d(a, b): return round(a / b, 4) if b else 0.0
        evidence_metrics = {"available": True, "evidence_tp": etp, "evidence_fp": efp, "evidence_fn": efn,
                            "precision": d(etp, etp + efp), "recall": d(etp, etp + efn),
                            "hallucinated_evidence_count": efp, "missing_expected_examples": missing_exp[:50]}
    else:
        evidence_metrics = {"available": False,
                            "note": "manifest 에 expected_evidence 컬럼이 없어 evidence 정밀도/재현율 미산출"}

    # ---------- 5. latency ----------
    latency = {}
    for kk in LAT_KEYS:
        vals = [r["lat"][kk] for r in rows if kk in r["lat"] and r["lat"][kk] is not None]
        if vals:
            latency[kk] = {"avg": round(sum(vals) / len(vals), 2), "p50": _pct(vals, 50),
                           "p90": _pct(vals, 90), "p95": _pct(vals, 95), "max": round(max(vals), 2), "n": len(vals)}
    if not latency:
        latency = {"note": "predictions 에 latency 필드 없음"}

    # ---------- 6. dataset hygiene ----------
    hygiene = {
        "manifest_total_rows": len(man), "evaluated_rows": len(rows),
        "excluded_rows": dict(excluded_rows),
        "source_count": dict(Counter(str(m.get("source_type", m.get("source", ""))) for m in man)),
        "task_count_evaluated": dict(Counter(r["task"] for r in rows)),
        "ground_truth_count_evaluated": dict(Counter(r["ground_truth"] for r in rows)),
        "synthetic_generated_contamination_count": len(hygiene_contam),
        "contamination_ids": hygiene_contam,
        "missing_image_count": excluded_rows.get("no_prediction", 0),  # 예측 없음(이미지→추론 누락)
        "duplicate_filename_hash_count": dup,
        "missing_prediction_ids": missing_pred[:50],
    }

    # ---------- 저장 ----------
    def dump(name, obj):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    dump("metrics_summary.json", {"run": args.run_name, "generated_at": datetime.now(timezone.utc).isoformat(),
                                  "task_level": metrics})
    dump("safety_summary.json", safety)
    dump("false_positive_cases.json", fps)
    dump("false_negative_cases.json", fns)
    dump("borderline_cases.json", borderline_cases)
    dump("evidence_metrics.json", evidence_metrics)
    dump("rule_diagnostics.json", rule_diag)
    dump("latency_summary.json", latency)
    dump("dataset_hygiene.json", hygiene)
    # metrics_summary.csv (primary mode, task별)
    with (out / "metrics_summary.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["scope", "n", "tp", "tn", "fp", "fn", "accuracy", "precision", "recall", "f1",
                "false_positive_rate", "false_negative_rate", "specificity", "negative_predictive_value"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for scope, mm in metrics[f"borderline_{primary_mode}"].items():
            w.writerow({"scope": scope, **{k: mm.get(k) for k in cols[1:]}})
    # per_image.csv
    with (out / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["image_id", "task", "ground_truth", "pred_result", "verified", "score",
                "mandatory_passed", "got_evidence", "rule_evidence"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({**{k: r.get(k) for k in cols[:7]},
                        "got_evidence": ";".join(r["got_evidence"]), "rule_evidence": ";".join(r["rule_evidence"])})
    _report_md(out, args, metrics, primary_mode, safety, rule_diag, evidence_metrics, latency, hygiene)

    # 콘솔
    print(f"[advanced-eval] run={args.run_name} evaluated={len(rows)} (manifest {len(man)})")
    print(f"  contamination={hygiene['synthetic_generated_contamination_count']} "
          f"missing_prediction={len(missing_pred)} dup={dup}")
    for scope in ("ALL", "water", "exercise", "study"):
        mm = metrics[f"borderline_{primary_mode}"].get(scope)
        if mm:
            print(f"  [{primary_mode}] {scope:9} n={mm['n']} FP={mm['fp']} FN={mm['fn']} "
                  f"acc={mm['accuracy']} rec={mm['recall']}")
    print(f"  SAFETY FP_count={safety['FP_count']} (as_fail FP={safety['borderline_as_fail_FP']}, "
          f"excluded FP={safety['borderline_excluded_FP']})")
    print(f"  [out] {out}")


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _score_hist(scores):
    if not scores:
        return {}
    buckets = Counter()
    for s in scores:
        b = int(s // 10) * 10
        buckets[f"{b}-{b+9}"] += 1
    return dict(sorted(buckets.items()))


def _report_md(out, args, metrics, mode, safety, rule_diag, evid, latency, hygiene):
    L = [f"# advanced eval — {args.run_name}", "",
         f"- evaluated rows: {hygiene['evaluated_rows']} / manifest {hygiene['manifest_total_rows']}",
         f"- borderline(primary): {mode}",
         f"- **contamination(synthetic/generated): {hygiene['synthetic_generated_contamination_count']}**",
         f"- missing prediction: {len(hygiene['missing_prediction_ids'])}, duplicate: {hygiene['duplicate_filename_hash_count']}",
         "", "## task-level (primary borderline mode)",
         "| scope | n | FP | FN | acc | prec | rec | f1 | FPR |", "|---|---|---|---|---|---|---|---|---|"]
    for scope, mm in metrics[f"borderline_{mode}"].items():
        L.append(f"| {scope} | {mm['n']} | {mm['fp']} | {mm['fn']} | {mm['accuracy']} | "
                 f"{mm['precision']} | {mm['recall']} | {mm['f1']} | {mm['false_positive_rate']} |")
    L += ["", "## safety-first",
          f"- **FP_count: {safety['FP_count']}** (verified_on_fail: {safety['verified_on_fail_count']})",
          f"- fail_open_rate: {safety['fail_open_rate']}",
          f"- FP_by_task: {safety['FP_by_task']}",
          f"- FP_by_rule_evidence: {safety['FP_by_rule_evidence']}",
          f"- borderline_as_fail FP={safety['borderline_as_fail_FP']} / borderline_excluded FP={safety['borderline_excluded_FP']}",
          "", "## rule diagnostics",
          f"- result: {rule_diag['result_distribution']}",
          f"- mandatory_passed_rate: {rule_diag['mandatory_passed_rate']}",
          f"- score_distribution: {rule_diag['score_distribution']}",
          "", "## evidence metrics", f"- {evid}",
          "", "## latency", f"- {latency}",
          "", "## 판정 관점",
          "- FP=0 최우선. FP>0 이면 라벨오류/parser/prompt/rule threshold/모델 hallucination 순으로 분석.",
          "- study FN 과다 → Qwen2.5-VL-3B-AWQ fallback 유지. VLM은 evidence만, 판정은 Rule Engine."]
    (out / "experiment_report.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
