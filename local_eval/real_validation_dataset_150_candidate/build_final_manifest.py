"""사용자 최종 검수 CSV → 모델 평가용 final_manifest 생성(엄격 필터).

입력: --input labeled_candidate_final_reviewed.csv (사용자 확정 라벨)
출력: final_manifest.csv / final_manifest.json / FINAL_DATASET_SUMMARY.md

필터(모두 통과해야 포함):
  include_in_eval == Y / task in {water,exercise,study} / ground_truth in {PASS,FAIL,BORDERLINE}
  / source != synthetic / filepath·name·source·notes 에 generated|synth|synthetic|ai-created 없음
  / exclude_reason 빈칸 / exclude_reason이 illustration_render·historical_document·irrelevant·low_quality·other 아님
  / 이미지 파일 존재 / 중복(파일명·해시) 아님.

contamination(합성/AI/일러스트가 include 로 남아있음)이 있으면 ERROR. 그 외 성공기준 미달은 WARNING.
입력 CSV(사용자 검수본)는 읽기만 한다(수정 안 함).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
OUT_CSV = THIS_DIR / "final_manifest.csv"
OUT_JSON = THIS_DIR / "final_manifest.json"
SUMMARY = THIS_DIR / "FINAL_DATASET_SUMMARY.md"

TASKS = {"water", "exercise", "study"}
GTS = {"PASS", "FAIL", "BORDERLINE"}
CONTAM_TOKENS = ("generated", "synth", "synthetic", "ai-created", "ai_created", "aigenerated")
BAD_REASONS = {"illustration_render", "historical_document", "irrelevant", "low_quality", "other"}
FINAL_FIELDS = ["image_id", "filepath", "task", "ground_truth", "suggested_ground_truth",
                "evidence_hint", "source_type", "source_site", "source_url", "author",
                "license_or_usage_note", "notes", "batch"]


def _contaminated(r: dict) -> bool:
    blob = " ".join(str(r.get(k, "")).lower() for k in ("filepath", "image_id", "source_type", "source_site", "notes"))
    return any(tok in blob for tok in CONTAM_TOKENS)


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(THIS_DIR / "labeled_candidate_final_reviewed.csv"))
    args = ap.parse_args()
    inp = Path(args.input)
    if not inp.exists():
        print(f"[error] 입력 CSV 없음: {inp}  (사용자 최종 검수 CSV 필요)")
        _write_summary({"error": f"input not found: {inp}"}, [])
        sys.exit(0)  # 스크립트 자체는 실패하지 않음

    rows = list(csv.DictReader(inp.open(encoding="utf-8")))
    total = len(rows)
    kept, dropped = [], Counter()
    contamination = []
    missing = 0
    seen_hash, seen_name, dup = {}, {}, 0

    for r in rows:
        gt = str(r.get("ground_truth", "")).strip().upper()
        task = str(r.get("task", "")).strip()
        inc = str(r.get("include_in_eval", "")).strip().upper()
        src = str(r.get("source_type", r.get("source", ""))).strip().lower()
        reason = str(r.get("exclude_reason", "")).strip()

        if _contaminated(r):                      # 오염은 include 여부와 무관하게 기록
            if inc == "Y":
                contamination.append(r.get("image_id", "?"))
        if inc != "Y": dropped["include!=Y"] += 1; continue
        if task not in TASKS: dropped["task_invalid"] += 1; continue
        if gt not in GTS: dropped["gt_not_final(UNLABELED/TODO/빈칸)"] += 1; continue
        if src == "synthetic": dropped["source_synthetic"] += 1; continue
        if _contaminated(r): dropped["contamination_token"] += 1; continue
        if reason: dropped[f"exclude_reason:{reason if reason in BAD_REASONS else 'other_nonempty'}"] += 1; continue
        p = THIS_DIR / r.get("filepath", "")
        if not p.exists(): dropped["missing_image"] += 1; missing += 1; continue
        # 중복(파일명/해시)
        name = Path(r.get("filepath", "")).name
        if name in seen_name: dropped["dup_filename"] += 1; dup += 1; continue
        try:
            h = _sha(p)
        except Exception: h = None  # noqa: BLE001
        if h and h in seen_hash: dropped["dup_hash"] += 1; dup += 1; continue
        seen_name[name] = 1
        if h: seen_hash[h] = 1
        kept.append(r)

    # 통계
    by_task = Counter(r["task"] for r in kept)
    by_gt = Counter(str(r["ground_truth"]).upper() for r in kept)
    pivot = Counter((r["task"], str(r["ground_truth"]).upper()) for r in kept)
    by_src = Counter(str(r.get("source_type", r.get("source", ""))) for r in kept)
    by_batch = Counter(r.get("batch", "") or "(none)" for r in kept)

    # 출력
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FINAL_FIELDS)
        w.writeheader()
        for r in kept:
            w.writerow({k: r.get(k, "") for k in FINAL_FIELDS})
    OUT_JSON.write_text(json.dumps([{k: r.get(k, "") for k in FINAL_FIELDS} for r in kept],
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "input": str(inp), "total_rows": total, "final_included": len(kept),
        "by_task": dict(by_task), "by_ground_truth": dict(by_gt),
        "pivot_task_x_gt": {f"{t}/{g}": n for (t, g), n in sorted(pivot.items())},
        "by_source": dict(by_src), "by_batch": dict(by_batch),
        "excluded_reasons": dict(dropped),
        "contamination_count": len(contamination), "contamination_ids": contamination,
        "missing_image_count": missing, "duplicate_count": dup,
    }
    # 성공기준 판정
    warns = []
    for t in ("water", "exercise", "study"):
        if by_task.get(t, 0) < 50:
            warns.append(f"{t} {by_task.get(t,0)} < 50 (목표 미달)")
    if by_gt.get("UNLABELED") or by_gt.get("TODO"):
        warns.append("UNLABELED/TODO 포함(있으면 안 됨)")  # 사실상 필터로 0
    stats["warnings"] = warns
    stats["contamination_error"] = len(contamination) > 0

    _write_summary(stats, kept)
    # 콘솔
    print(f"[build_final_manifest] input={inp.name} total={total} → final_included={len(kept)}")
    print(f"  by_task={dict(by_task)}  by_gt={dict(by_gt)}")
    print(f"  pivot={stats['pivot_task_x_gt']}")
    print(f"  by_source={dict(by_src)}  by_batch={dict(by_batch)}")
    print(f"  excluded_reasons={dict(dropped)}")
    print(f"  missing_image={missing} duplicates={dup}")
    if stats["contamination_error"]:
        print(f"  [ERROR] synthetic/generated/AI contamination in include=Y: {len(contamination)} → {contamination}")
    for wmsg in warns:
        print(f"  [WARNING] {wmsg}")
    if not warns and not stats["contamination_error"]:
        print("  [OK] 성공기준 충족(각 task>=50, contamination=0, UNLABELED/N 없음).")
    print(f"  [out] {OUT_CSV.name}, {OUT_JSON.name}, {SUMMARY.name}")


def _write_summary(stats: dict, kept: list[dict]) -> None:
    L = ["# FINAL_DATASET_SUMMARY", ""]
    if stats.get("error"):
        L += [f"입력 오류: {stats['error']}", "", "사용자 최종 검수 CSV(labeled_candidate_final_reviewed.csv)를 준비 후 재실행."]
        SUMMARY.write_text("\n".join(L), encoding="utf-8"); return
    L += [f"- input: {stats['input']}",
          f"- total rows: {stats['total_rows']}",
          f"- final included: **{stats['final_included']}**", "",
          "## task별", *[f"- {t}: {n}" for t, n in stats["by_task"].items()],
          "", "## ground_truth별", *[f"- {g}: {n}" for g, n in stats["by_ground_truth"].items()],
          "", "## task × ground_truth", *[f"- {k}: {n}" for k, n in stats["pivot_task_x_gt"].items()],
          "", "## source별", *[f"- {s}: {n}" for s, n in stats["by_source"].items()],
          "", "## batch별", *[f"- {b}: {n}" for b, n in stats["by_batch"].items()],
          "", "## 제외 사유별", *[f"- {r}: {n}" for r, n in stats["excluded_reasons"].items()],
          "", "## hygiene",
          f"- synthetic/generated/AI contamination(include=Y): **{stats['contamination_count']}** "
          f"{'← ERROR' if stats['contamination_error'] else '(OK)'}",
          f"- missing image: {stats['missing_image_count']}",
          f"- duplicate(filename/hash): {stats['duplicate_count']}",
          "", "## 성공기준 판정"]
    if stats["contamination_error"]:
        L.append(f"- ❌ ERROR: contamination {stats['contamination_count']} (ids: {stats['contamination_ids']})")
    for wmsg in stats.get("warnings", []):
        L.append(f"- ⚠️ WARNING: {wmsg}")
    if not stats.get("warnings") and not stats["contamination_error"]:
        L.append("- ✅ OK: 각 task>=50, contamination=0, UNLABELED/TODO/include=N 없음")
    SUMMARY.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
