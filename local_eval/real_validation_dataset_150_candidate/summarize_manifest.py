"""사용자 검수 후(또는 검수 전 현재상태) manifest 집계 + 부족분 타겟 수집계획 생성.

입력: manifest_unlabeled.json (기본) 또는 --manifest <csv|json> (labeling page 저장본).
출력(콘솔 + summary.json + GAP_PLAN.md):
  1. task별 include_in_eval=Y 수량
  2. task별 PASS/FAIL/BORDERLINE/UNLABELED 수량(include=Y 기준)
  3. 부족한 task / 부족한 PASS·FAIL 유형(목표 대비)
  4. 부족분에 대해서만 Commons/from-csv 추가 수집 계획

목표(기본, 변경 가능): task당 총 50 = PASS 25 / FAIL 20 / BORDERLINE 5.
원칙: synthetic/AI/illustration/무관은 include=N(exclude_reason 기록)으로 이미 걸러진 것만 집계.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
TASKS = ("water", "exercise", "study")
TARGET_TOTAL = 50
TARGET_MIX = {"PASS": 25, "FAIL": 20, "BORDERLINE": 5}  # 가이드라인(합 50)

# 부족분 수집용 쿼리 힌트(원 스펙 카테고리 기반). 실제 사진만, 검수 필수.
QUERY_HINTS = {
    "water": {
        "PASS": ["glass of water", "pouring water into glass", "person drinking water",
                 "water bottle transparent", "pitcher of water"],
        "FAIL": ["cup of coffee", "glass of juice", "cola glass", "cup of tea", "empty glass",
                 "empty bottle", "milk glass", "smoothie glass"],
    },
    "exercise": {
        "PASS": ["dumbbell", "barbell", "kettlebell", "treadmill", "person doing squat",
                 "yoga mat exercise", "gym interior", "weight machine"],
        "FAIL": ["office desk laptop", "running shoes", "empty room", "person sitting chair",
                 "bedroom interior", "water bottle only"],
    },
    "study": {
        "PASS": ["open textbook", "handwriting notebook", "student writing", "worksheet math",
                 "coding screen", "lecture slides", "highlighted notes"],
        "FAIL": ["video game screen", "social media feed", "youtube screen", "movie screen",
                 "online shopping website", "empty desk"],
    },
}


def _load(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=str(THIS_DIR / "manifest_unlabeled.json"))
    ap.add_argument("--target-total", type=int, default=TARGET_TOTAL)
    args = ap.parse_args()

    rows = _load(Path(args.manifest))
    inc = [r for r in rows if str(r.get("include_in_eval", "Y")).upper() == "Y"]
    exc = [r for r in rows if str(r.get("include_in_eval", "Y")).upper() == "N"]

    # 1) task별 include=Y
    by_task_inc = Counter(r.get("task") for r in inc)
    # 2) task별 gt 분포(include=Y)
    gt_by_task = {t: Counter() for t in (*TASKS, "UNLABELED")}
    for r in inc:
        gt_by_task.setdefault(r.get("task"), Counter())[str(r.get("ground_truth") or "UNLABELED").upper()] += 1
    # exclude 사유 분포
    exc_reason = Counter(r.get("exclude_reason") or "(none)" for r in exc)
    intake_unlabeled = by_task_inc.get("UNLABELED", 0)
    # batch 분포 (initial vs gap_fill_02 등)
    by_batch = Counter((r.get("batch") or "initial") for r in rows)
    by_batch_inc = Counter((r.get("batch") or "initial") for r in inc)
    # gap_fill_02 의 suggested 분포(task x suggested) — 이번 수집 커버리지
    gapfill = Counter((r.get("task"), r.get("suggested_ground_truth") or "-")
                      for r in inc if (r.get("batch") or "") == "gap_fill_02")

    # 3~4) 부족분 + 계획
    plan = {}
    for t in TASKS:
        g = gt_by_task.get(t, Counter())
        cur_total = by_task_inc.get(t, 0)
        need_total = max(0, args.target_total - cur_total)
        need_pass = max(0, TARGET_MIX["PASS"] - g.get("PASS", 0))
        need_fail = max(0, TARGET_MIX["FAIL"] - g.get("FAIL", 0))
        need_bord = max(0, TARGET_MIX["BORDERLINE"] - g.get("BORDERLINE", 0))
        plan[t] = {
            "current_included": cur_total,
            "labeled": {k: g.get(k, 0) for k in ("PASS", "FAIL", "BORDERLINE")},
            "unlabeled_in_task": g.get("UNLABELED", 0),
            "need_total_to_target": need_total,
            "need_by_type": {"PASS": need_pass, "FAIL": need_fail, "BORDERLINE": need_bord},
            "suggested_commons_queries": {
                "PASS": QUERY_HINTS[t]["PASS"], "FAIL": QUERY_HINTS[t]["FAIL"]},
        }

    summary = {
        "manifest": str(args.manifest), "total_rows": len(rows),
        "included": len(inc), "excluded": len(exc),
        "target_per_task": args.target_total, "target_mix": TARGET_MIX,
        "included_by_task": dict(by_task_inc),
        "ground_truth_by_task": {t: dict(gt_by_task.get(t, {})) for t in (*TASKS, "UNLABELED")},
        "exclude_reasons": dict(exc_reason),
        "intake_unlabeled_needing_task": intake_unlabeled,
        "by_batch_all": dict(by_batch), "by_batch_included": dict(by_batch_inc),
        "gap_fill_02_included_by_task_suggested": {f"{t}/{s}": n for (t, s), n in sorted(gapfill.items())},
        "gap_plan": plan,
    }
    (THIS_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_gap_plan_md(summary)

    # 콘솔
    print(f"[manifest] {args.manifest}  total={len(rows)} included={len(inc)} excluded={len(exc)}")
    print(f"[1] include=Y per task: {dict(by_task_inc)}")
    print("[2] ground_truth per task (include=Y):")
    for t in TASKS:
        print(f"    {t:9} {dict(gt_by_task.get(t, {}))}")
    if intake_unlabeled:
        print(f"    (intake UNLABELED task 미분류: {intake_unlabeled}장 → labeling page 에서 task 지정 필요)")
    if exc:
        print(f"[exclude] {len(exc)}장 excluded, 사유: {dict(exc_reason)}")
    print(f"[batch] all={dict(by_batch)} | included={dict(by_batch_inc)}")
    if gapfill:
        print(f"[gap_fill_02] include=Y task/suggested: {summary['gap_fill_02_included_by_task_suggested']}")
    print("[3+4] 부족분 & 수집계획 (목표 task당 "
          f"{args.target_total} = PASS{TARGET_MIX['PASS']}/FAIL{TARGET_MIX['FAIL']}/BORDER{TARGET_MIX['BORDERLINE']}):")
    for t in TASKS:
        p = plan[t]
        print(f"    {t:9} 현재 include {p['current_included']} / 라벨 {p['labeled']} "
              f"→ 부족 total {p['need_total_to_target']} (PASS {p['need_by_type']['PASS']}, "
              f"FAIL {p['need_by_type']['FAIL']}, BORDER {p['need_by_type']['BORDERLINE']})")
    print(f"[out] summary.json, GAP_PLAN.md")


def _write_gap_plan_md(s: dict) -> None:
    L = ["# GAP_PLAN — 부족분 타겟 수집 계획", "",
         f"목표: task당 {s['target_per_task']} (가이드 PASS{s['target_mix']['PASS']}/"
         f"FAIL{s['target_mix']['FAIL']}/BORDERLINE{s['target_mix']['BORDERLINE']}). "
         "실제 사진만, 수집 후 contact sheet/labeling 검수 필수.", "",
         f"현재 included_by_task: {s['included_by_task']}  (excluded {s['excluded']}, "
         f"intake 미분류 {s['intake_unlabeled_needing_task']})", ""]
    for t in TASKS:
        p = s["gap_plan"][t]
        L += [f"## {t}",
              f"- 현재 include={p['current_included']}, 라벨 {p['labeled']}, task내 UNLABELED {p['unlabeled_in_task']}",
              f"- **부족: 총 {p['need_total_to_target']} (PASS {p['need_by_type']['PASS']} / "
              f"FAIL {p['need_by_type']['FAIL']} / BORDERLINE {p['need_by_type']['BORDERLINE']})**",
              "- PASS 수집 쿼리(Commons) 예: " + ", ".join(f"`{q}`" for q in p["suggested_commons_queries"]["PASS"]),
              "- FAIL 수집 쿼리(Commons) 예: " + ", ".join(f"`{q}`" for q in p["suggested_commons_queries"]["FAIL"]),
              f"- 실행: `python collect_images.py from-commons --task {t} --query \"<위 쿼리>\" --count 8` "
              "(호출 간 2초 간격) / 또는 Pexels·Unsplash 선별 후 `from-csv`.", ""]
    L += ["## 공통 절차",
          "1) intake(UNLABELED) 를 labeling page 에서 task 지정(부족분 우선 충당).",
          "2) 위 부족 유형(PASS/FAIL)만 겨냥해 수집.",
          "3) contact sheet 재생성 → AI/illustration/무관 include=N(exclude_reason).",
          "4) labeling page 에서 ground_truth 확정 후 이 스크립트 재실행."]
    (THIS_DIR / "GAP_PLAN.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
