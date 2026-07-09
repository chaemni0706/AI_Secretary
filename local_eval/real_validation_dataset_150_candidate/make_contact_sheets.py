"""task별 contact sheet(썸네일 격자 PNG) 생성 — 사용자가 '사진인지/내용'을 눈으로 검수하게 한다.

manifest_unlabeled.json 을 읽어 task(water/exercise/study/UNLABELED)별로 이미지를 격자로 배치,
파일명+image_id 를 캡션으로 달아 contact_sheets/<task>_NN.png 로 저장. (PIL 사용, 다운로드 없음)

목적: AI/illustration/무관 이미지를 사람이 골라 excluded/ 로 빼도록 시각 검수 제공.
"""

from __future__ import annotations

import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
MANIFEST = THIS_DIR / "manifest_unlabeled.json"
OUT = THIS_DIR / "contact_sheets"

COLS, THUMB, PAD, CAP = 6, 220, 10, 26  # 격자 6열, 썸네일 220px, 캡션 26px


def main() -> None:
    from PIL import Image, ImageDraw
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for task, items in by_task.items():
        per_page = COLS * 6  # 36장/페이지
        for pg in range((len(items) + per_page - 1) // per_page):
            chunk = items[pg * per_page:(pg + 1) * per_page]
            rows_n = (len(chunk) + COLS - 1) // COLS
            W = COLS * (THUMB + PAD) + PAD
            H = rows_n * (THUMB + CAP + PAD) + PAD
            sheet = Image.new("RGB", (W, H), (245, 245, 245))
            d = ImageDraw.Draw(sheet)
            for i, r in enumerate(chunk):
                cx = PAD + (i % COLS) * (THUMB + PAD)
                cy = PAD + (i // COLS) * (THUMB + CAP + PAD)
                p = THIS_DIR / r["filepath"]
                try:
                    im = Image.open(p).convert("RGB")
                    im.thumbnail((THUMB, THUMB))
                    sheet.paste(im, (cx + (THUMB - im.width) // 2, cy + (THUMB - im.height) // 2))
                except Exception:  # noqa: BLE001
                    d.rectangle([cx, cy, cx + THUMB, cy + THUMB], outline=(200, 0, 0))
                    d.text((cx + 4, cy + 4), "LOAD FAIL", fill=(200, 0, 0))
                d.rectangle([cx, cy, cx + THUMB, cy + THUMB], outline=(180, 180, 180))
                d.text((cx + 2, cy + THUMB + 4), f"{r['image_id']} [{r['source_type'][:4]}]", fill=(20, 20, 20))
                d.text((cx + 2, cy + THUMB + 14), Path(r["filepath"]).name[:34], fill=(90, 90, 90))
            outp = OUT / f"{task}_{pg+1:02d}.png"
            sheet.save(outp)
            made.append((outp, len(chunk)))
    for p, n in made:
        print(f"[contact-sheet] {p}  ({n} imgs)")
    if not made:
        print("[contact-sheet] no images in manifest yet")


if __name__ == "__main__":
    main()
