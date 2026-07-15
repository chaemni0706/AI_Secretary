"""사용자 최종 수집 이미지(39장) → manifest_unlabeled 안전 편입.

파일명 prefix 로 task/suggested_ground_truth 를 추정하되, **ground_truth 는 확정하지 않는다**(UNLABELED).
실제 사진만 전제(사용자 수집 책임 + 이후 labeling 검수). synthetic/AI/illustration 은 편입하지 않음(옵션 없음).
기존 labeled_candidate_*_reviewed.csv 는 절대 수정하지 않는다.

파일명 규칙:
  exercise_fail_NN.jpg      → task=exercise, suggested=FAIL
  exercise_borderline_NN.*  → task=exercise, suggested=BORDERLINE
  study_pass_NN.*           → task=study,    suggested=PASS
  study_fail_NN.*           → task=study,    suggested=FAIL
  study_borderline_NN.*     → task=study,    suggested=BORDERLINE
  (water_* 도 동일 규칙 지원하나 이번 목표엔 없음)

실행:
  python import_final_user_images.py --input-dir final_user_collect [--manifest manifest_unlabeled.csv] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
IMAGES = THIS_DIR / "images"
DEST_SUBDIR = "final_user_collect"
MANIFEST_JSON = THIS_DIR / "manifest_unlabeled.json"
MANIFEST_CSV = THIS_DIR / "manifest_unlabeled.csv"
REPORT = THIS_DIR / "IMPORT_FINAL_USER_IMAGES_REPORT.md"
BATCH = "final_user_collect"

FIELDS = ["image_id", "filepath", "task", "ground_truth", "suggested_ground_truth",
          "evidence_hint", "source_type", "source_site", "source_url", "author",
          "license_or_usage_note", "include_in_eval", "exclude_reason", "notes",
          "needs_user_review", "batch"]

_EXT = {".jpg", ".jpeg", ".png"}
_TASKS = {"water", "exercise", "study"}
_SUG = {"pass": "PASS", "fail": "FAIL", "borderline": "BORDERLINE"}
# exercise_fail_01 / study_pass_03 ...
_NAME_RE = re.compile(r"^(water|exercise|study)_(pass|fail|borderline)_\w+$", re.IGNORECASE)


def _load_manifest() -> list[dict]:
    if MANIFEST_JSON.exists():
        rows = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        for r in rows:
            for k in FIELDS:
                r.setdefault(k, "")
        return rows
    return []


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _existing_hashes(rows: list[dict]) -> dict[str, str]:
    """이미 편입된 final_user_collect 이미지의 해시(중복 재편입 방지)."""
    out = {}
    for r in rows:
        if r.get("batch") == BATCH:
            p = THIS_DIR / r.get("filepath", "")
            if p.exists():
                out[_sha256(p)] = r["image_id"]
    return out


def _entry(image_id, rel, task, suggested) -> dict:
    return {
        "image_id": image_id, "filepath": rel, "task": task, "ground_truth": "UNLABELED",
        "suggested_ground_truth": suggested,
        "evidence_hint": f"user-collected {task}/{suggested}; confirm via labeling page",
        "source_type": "user_collect", "source_site": "user", "source_url": "", "author": "",
        "license_or_usage_note": "user-owned (self-collected real photo)",
        "include_in_eval": "Y", "exclude_reason": "", "notes": BATCH,
        "needs_user_review": "Y", "batch": BATCH,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", default=str(THIS_DIR / DEST_SUBDIR))
    ap.add_argument("--manifest", default=str(MANIFEST_CSV))  # 정보용(실제 소스는 json)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    added, skipped, errors, plan = [], [], [], []
    rows = _load_manifest()
    existing_ids = {r["image_id"] for r in rows}
    existing_names = {Path(r.get("filepath", "")).name for r in rows}
    seen_hashes = _existing_hashes(rows)
    new_hashes: dict[str, str] = {}

    if not in_dir.exists():
        errors.append(f"입력 폴더 없음: {in_dir}")
    files = sorted(in_dir.iterdir()) if in_dir.exists() else []
    img_files = [f for f in files if f.is_file()]

    for f in img_files:
        stem, ext = f.stem, f.suffix.lower()
        if ext not in _EXT:
            errors.append(f"확장자 오류(무시): {f.name} (허용 {sorted(_EXT)})")
            continue
        if not _NAME_RE.match(stem):
            errors.append(f"파일명 규칙 불일치(무시): {f.name} (예: exercise_fail_01.jpg)")
            continue
        t, s = stem.split("_")[0].lower(), stem.split("_")[1].lower()
        task, suggested = t, _SUG[s]
        if f.name in existing_names or stem in existing_ids:
            skipped.append(f"{f.name} (이미 manifest 에 존재)")
            continue
        try:
            h = _sha256(f)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"해시 실패(무시): {f.name}: {exc}")
            continue
        if h in seen_hashes:
            skipped.append(f"{f.name} (해시 중복: 기존 {seen_hashes[h]})")
            continue
        if h in new_hashes:
            skipped.append(f"{f.name} (해시 중복: 입력 내 {new_hashes[h]})")
            continue
        new_hashes[h] = stem
        plan.append((f, stem, task, suggested))

    # dry-run: 계획만 출력, 파일/매니페스트 미변경
    if args.dry_run:
        _report(added=[], plan=plan, skipped=skipped, errors=errors, dry=True, total_after=len(rows))
        print(f"[dry-run] 편입 예정 {len(plan)}장, skip {len(skipped)}, error {len(errors)} — 변경 없음")
        return

    if not plan:
        _report(added=[], plan=[], skipped=skipped, errors=errors, dry=False, total_after=len(rows))
        print(f"[import] 편입할 유효 이미지 없음 (skip {len(skipped)}, error {len(errors)}). manifest 변경 없음.")
        return

    # 백업 후 편입
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for p in (MANIFEST_JSON, MANIFEST_CSV):
        if p.exists():
            shutil.copy2(p, p.with_suffix(p.suffix + f".{ts}.bak"))
    dest = IMAGES / DEST_SUBDIR
    dest.mkdir(parents=True, exist_ok=True)
    for f, stem, task, suggested in plan:
        rel = f"images/{DEST_SUBDIR}/{stem}{f.suffix.lower()}"
        try:
            shutil.copy2(f, THIS_DIR / rel)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"복사 실패: {f.name}: {exc}")
            continue
        rows.append(_entry(stem, rel, task, suggested))
        added.append((stem, task, suggested))

    MANIFEST_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    _report(added=added, plan=plan, skipped=skipped, errors=errors, dry=False, total_after=len(rows), ts=ts)
    print(f"[import] 편입 {len(added)}장, skip {len(skipped)}, error {len(errors)}. manifest total={len(rows)} (backup .{ts}.bak)")


def _report(added, plan, skipped, errors, dry, total_after, ts=None) -> None:
    from collections import Counter
    src = plan if dry else [(None, s, t, g) for (s, t, g) in added]
    by = Counter((t, g) for (_f, _s, t, g) in (plan if dry else [(None, a[0], a[1], a[2]) for a in added]))
    L = [f"# import_final_user_images 리포트 ({'DRY-RUN' if dry else 'APPLIED'})", "",
         f"- 생성 시각: {ts or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
         f"- {'편입 예정' if dry else '편입 완료'}: {len(plan) if dry else len(added)}장",
         f"- skip(중복 등): {len(skipped)}",
         f"- error(확장자/규칙/복사): {len(errors)}",
         f"- manifest total(편입 후): {total_after}", "",
         "## task × suggested_ground_truth"]
    for (t, g), n in sorted(by.items()):
        L.append(f"- {t} / {g}: {n}")
    if skipped:
        L += ["", "## skipped"] + [f"- {s}" for s in skipped]
    if errors:
        L += ["", "## errors"] + [f"- {e}" for e in errors]
    L += ["", "## 원칙", "- ground_truth=UNLABELED (사용자 확정 전까지 미확정)",
          "- batch=final_user_collect, needs_user_review=Y, include_in_eval=Y",
          "- synthetic/AI/illustration 미편입(옵션 없음). 실제 사진 전제.",
          "- labeled_candidate_*_reviewed.csv 는 수정하지 않음."]
    REPORT.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
