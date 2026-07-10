"""real-only 150 candidate 데이터셋 수집기 (water/exercise/study 각 50 목표).

원칙(엄수):
- **실제 사람이 촬영한 사진만.** AI/GPT/synthetic/generated/illustration/render/cartoon/icon/mockup 금지.
- 이미지마다 source_url / source_site / license_or_usage_note 를 정확히 기록(날조 금지).
- ground_truth 는 UNLABELED 로 두고 suggested_ground_truth 만 채운다(최종 라벨은 사용자 확정).
- 에이전트는 이미지를 눈으로 볼 수 없으므로, 인터넷 수집분은 needs_user_review=Y 로 두고
  contact sheet/labeling page 에서 사용자가 사진 여부·내용·라벨을 최종 검수한다.

서브커맨드:
  ingest-user   : 사용자 실제 촬영 사진 편입(보존)
                  - data/test_images/water/uploaded/*.png (task=water, 실제 업로드 사진)
                  - real_validation_dataset/images/real_zflip/*.jpg (task=UNLABELED → _intake_unclassified)
  from-commons  : Wikimedia Commons(오픈 API, 정확한 source_url+license)에서 후보 사진 다운로드
                  예: --task water --query "glass of water" --count 12
  from-csv      : 사용자가 준비한 CSV(url,license...)로 다운로드(Pexels/Unsplash 등 직접 수집분)

manifest(단일 소스): manifest_unlabeled.json (+ manifest_unlabeled.csv 자동 생성).
generated/synthetic 은 절대 넣지 않는다. 의심분은 excluded/ 로 사용자가 이동.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
IMAGES = THIS_DIR / "images"
MANIFEST_JSON = THIS_DIR / "manifest_unlabeled.json"
MANIFEST_CSV = THIS_DIR / "manifest_unlabeled.csv"

FIELDS = ["image_id", "filepath", "task", "ground_truth", "suggested_ground_truth",
          "evidence_hint", "source_type", "source_site", "source_url", "author",
          "license_or_usage_note", "include_in_eval", "exclude_reason", "notes",
          "needs_user_review", "batch"]

TASKS = ("water", "exercise", "study")
_PHOTO_EXT = {".jpg", ".jpeg", ".png"}  # svg/gif 제외(도식/애니 위험)


def _load() -> list[dict]:
    if MANIFEST_JSON.exists():
        rows = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        for r in rows:  # 필드 추가(exclude_reason 등) 시 backfill
            for k in FIELDS:
                r.setdefault(k, "")
        return rows
    return []


def _save(rows: list[dict]) -> None:
    MANIFEST_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def _seen_keys(rows) -> set:
    # 중복 방지 키: source_url 과 notes(예: user_upload:<name>, commons:<title>) 를 모두 포함.
    keys = set()
    for r in rows:
        for v in (r.get("source_url"), r.get("notes")):
            if v:
                keys.add(v)
    return keys


def _next_idx(rows, task) -> int:
    n = 0
    for r in rows:
        if r.get("task") == task and (r.get("image_id") or "").split("_")[0] == task:
            try:
                n = max(n, int(r["image_id"].split("_")[1]))
            except (IndexError, ValueError):
                pass
    return n + 1


def _entry(image_id, filepath, task, suggested, hint, src_type, site, url, lic, notes,
           author="", batch="") -> dict:
    return {
        "image_id": image_id, "filepath": filepath, "task": task,
        "ground_truth": "UNLABELED", "suggested_ground_truth": suggested,
        "evidence_hint": hint, "source_type": src_type, "source_site": site,
        "source_url": url, "author": author, "license_or_usage_note": lic,
        "include_in_eval": "Y", "exclude_reason": "", "notes": notes,
        "needs_user_review": "Y", "batch": batch,
    }


# --------------------------------------------------------------------------- #
# ingest-user
# --------------------------------------------------------------------------- #

def cmd_ingest_user(rows: list[dict]) -> None:
    seen = _seen_keys(rows)
    # 1) 실제 업로드 water 사진 (data/test_images/water/uploaded) — 실제 촬영본
    wm = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
    suggested_by_file = {}
    if wm.exists():
        for e in json.loads(wm.read_text(encoding="utf-8")).get("images", []):
            if e.get("source") == "uploaded":
                suggested_by_file[Path(e["image_path"]).name] = e.get("expected_label", "")
    up_dir = ROOT / "data" / "test_images" / "water" / "uploaded"
    added_w = 0
    for src in sorted(up_dir.glob("*.png")) if up_dir.exists() else []:
        key = f"user_upload:{src.name}"
        if key in seen:
            continue
        idx = _next_idx(rows, "water")
        dst_rel = f"images/water/water_{idx:03d}{src.suffix.lower()}"
        (THIS_DIR / dst_rel).parent.mkdir(parents=True, exist_ok=True)
        _copy(src, THIS_DIR / dst_rel)
        rows.append(_entry(f"water_{idx:03d}", dst_rel, "water",
                           suggested_by_file.get(src.name, ""),
                           "user-captured water photo", "user_upload", "local",
                           f"file://{src}", "user-owned (self-captured, real photo)", key))
        seen.add(key); added_w += 1

    # 2) real_zflip (실제 촬영, task 미상) → _intake_unclassified
    zf = ROOT / "local_eval" / "real_validation_dataset" / "images" / "real_zflip"
    added_z = 0
    for src in sorted(zf.glob("*.jpg")) if zf.exists() else []:
        key = f"user_upload:{src.name}"
        if key in seen:
            continue
        n = sum(1 for r in rows if r["task"] == "UNLABELED") + 1
        dst_rel = f"images/_intake_unclassified/intake_{n:03d}{src.suffix.lower()}"
        (THIS_DIR / dst_rel).parent.mkdir(parents=True, exist_ok=True)
        _copy(src, THIS_DIR / dst_rel)
        rows.append(_entry(f"intake_{n:03d}", dst_rel, "UNLABELED", "",
                           "self-captured; assign task+label via labeling page",
                           "user_upload", "local", f"file://{src}",
                           "user-owned (self-captured, real photo)", key))
        seen.add(key); added_z += 1
    print(f"[ingest-user] water uploaded +{added_w}, real_zflip(intake) +{added_z}")


def _copy(src: Path, dst: Path) -> None:
    import shutil
    shutil.copy2(src, dst)


# --------------------------------------------------------------------------- #
# from-commons (Wikimedia Commons open API — 정확한 provenance)
# --------------------------------------------------------------------------- #

def _curl_json(url: str) -> dict:
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "30",
                              "-H", "User-Agent: ai-secretary-validation/1.0 (research)", url],
                             capture_output=True, text=True, timeout=40)
        return json.loads(out.stdout)
    except Exception:  # noqa: BLE001
        return {}


def cmd_from_commons(rows: list[dict], task: str, query: str, count: int, suggested: str = "",
                     batch: str = "") -> None:
    api = "https://commons.wikimedia.org/w/api.php"
    s = _curl_json(f"{api}?action=query&format=json&list=search&srnamespace=6"
                   f"&srlimit={count*3}&srsearch={_q(query)}")
    titles = [m["title"] for m in s.get("query", {}).get("search", [])]
    seen = _seen_keys(rows)
    added = 0
    for title in titles:
        if added >= count:
            break
        info = _curl_json(f"{api}?action=query&format=json&prop=imageinfo&titles={_q(title)}"
                          "&iiprop=url|extmetadata|mime&iiurlwidth=768")
        pages = info.get("query", {}).get("pages", {})
        for _, p in pages.items():
            ii = (p.get("imageinfo") or [{}])[0]
            mime = ii.get("mime", "")
            thumb = ii.get("thumburl") or ii.get("url")
            desc = ii.get("descriptionurl", "")
            if not thumb or not mime.startswith("image/") or "svg" in mime:
                continue
            ext = Path(thumb.split("?")[0]).suffix.lower()
            if ext not in _PHOTO_EXT:
                continue
            if desc in seen:
                continue
            em = ii.get("extmetadata", {}) or {}
            lic = (em.get("LicenseShortName", {}) or {}).get("value", "see source")
            artist = (em.get("Artist", {}) or {}).get("value", "")
            artist = _strip_html(artist)[:80]
            idx = _next_idx(rows, task)
            dst_rel = f"images/{task}/{task}_{idx:03d}{ext}"
            if not _download(thumb, THIS_DIR / dst_rel):
                continue
            note = f"commons:{title}"
            if batch:
                note += f" | {batch}"
            rows.append(_entry(f"{task}_{idx:03d}", dst_rel, task, suggested,
                               f"commons candidate for {task}/{suggested or '?'}: '{query}'", "internet_real",
                               "Wikimedia Commons", desc, lic, note, author=artist, batch=batch))
            seen.add(desc); added += 1
    print(f"[from-commons] task={task} sug={suggested or '-'} query='{query}' → +{added} (needs_user_review=Y)")


def _download(url: str, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", "60",
                            "-H", "User-Agent: ai-secretary-validation/1.0 (research)",
                            "-o", str(dst), url], timeout=70)
        return dst.exists() and dst.stat().st_size > 2000
    except Exception:  # noqa: BLE001
        return False


def _q(s: str) -> str:
    from urllib.parse import quote
    return quote(s)


def _strip_html(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s or "").strip()


# --------------------------------------------------------------------------- #
# from-csv (user-provided urls: Pexels/Unsplash 등 직접 수집분)
# --------------------------------------------------------------------------- #

def cmd_from_csv(rows: list[dict], csv_path: Path) -> None:
    seen = _seen_keys(rows)
    added = 0
    for row in csv.DictReader(csv_path.open(encoding="utf-8")):
        task = (row.get("task") or "").strip()
        url = (row.get("source_url") or row.get("download_url") or "").strip()
        if task not in TASKS or not url or url in seen:
            continue
        ext = Path(url.split("?")[0]).suffix.lower()
        if ext not in _PHOTO_EXT:
            ext = ".jpg"
        idx = _next_idx(rows, task)
        dst_rel = f"images/{task}/{task}_{idx:03d}{ext}"
        if not _download(url, THIS_DIR / dst_rel):
            print(f"  [warn] download failed: {url}")
            continue
        rows.append(_entry(f"{task}_{idx:03d}", dst_rel, task,
                           (row.get("suggested_ground_truth") or "").strip(),
                           (row.get("evidence_hint") or "").strip(), "internet_real",
                           (row.get("source_site") or "").strip(), url,
                           (row.get("license_or_usage_note") or "user-recorded").strip(),
                           (row.get("notes") or "").strip(),
                           author=(row.get("author") or "").strip()))
        seen.add(url); added += 1
    print(f"[from-csv] +{added}")


# --------------------------------------------------------------------------- #

def _report(rows):
    from collections import Counter
    by_task = Counter(r["task"] for r in rows)
    by_src = Counter(r["source_type"] for r in rows)
    print("\n[manifest] total", len(rows))
    for t in (*TASKS, "UNLABELED"):
        print(f"  task={t:10} {by_task.get(t,0)}")
    print("  by source_type:", dict(by_src))
    for t in TASKS:
        print(f"  gap {t}: need {max(0,50-by_task.get(t,0))} more (target 50)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_argument_group("subcommand")
    ap.add_argument("cmd", choices=["ingest-user", "from-commons", "from-csv", "report"])
    ap.add_argument("--task", choices=list(TASKS))
    ap.add_argument("--query")
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--suggested", default="", choices=["", "PASS", "FAIL", "BORDERLINE"],
                    help="from-commons: 이 쿼리로 모은 후보의 suggested_ground_truth")
    ap.add_argument("--batch", default="", help="새 이미지 batch 태그(예: gap_fill_02)")
    ap.add_argument("--csv")
    args = ap.parse_args()

    rows = _load()
    if args.cmd == "ingest-user":
        cmd_ingest_user(rows)
    elif args.cmd == "from-commons":
        if not args.task or not args.query:
            raise SystemExit("--task 와 --query 필요")
        cmd_from_commons(rows, args.task, args.query, args.count, args.suggested, args.batch)
    elif args.cmd == "from-csv":
        if not args.csv:
            raise SystemExit("--csv 필요")
        cmd_from_csv(rows, Path(args.csv))
    _save(rows)
    _report(rows)


if __name__ == "__main__":
    main()
