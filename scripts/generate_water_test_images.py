"""Synthetic water-verification test-image generator.

목적
----
Qwen2.5-VL-3B 기반 물 인증 파이프라인(VLM 증거 추출 → VisionAnalysis 정규화 →
Rule Engine)과 PASS/FAIL 판정 로직을 비용 없이 검증하기 위한 합성 이미지를 만든다.

실제 사진 생성 API 없이 PIL 도형만으로 물컵 / 빈컵 / 정수기 / 물병 / 커피 상황을
시각적으로 구분되게 그린다. 픽셀 자체를 실제 VLM으로 판독하려는 것이 아니라,
사람이 봐도 상황이 구분되고, 라벨/매니페스트와 1:1로 대응되는 픽스처를 확보하는 것이 목표다.

사용법
------
    # 요구된 10장(generated/)만 생성
    python scripts/generate_water_test_images.py

    # 업로드 슬롯(uploaded/) 8장 placeholder까지 함께 생성
    python scripts/generate_water_test_images.py --uploaded-placeholders

출력 경로
---------
    data/test_images/water/generated/generated_water_01_full_glass.png ... _10_...png
    data/test_images/water/uploaded/water_test_01.png ... water_test_08.png (placeholder)

주의
----
uploaded/ 이미지는 사용자가 제공한 실제 인증사진 자리다. 실제 사진이 제공되지
않았기 때문에 여기서는 상황을 묘사한 placeholder를 그려 넣고 "PLACEHOLDER" 워터마크를
찍는다. 실제 photo가 준비되면 같은 파일명으로 교체하면 매니페스트/테스트가 그대로 동작한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WATER_DIR = ROOT / "data" / "test_images" / "water"
GENERATED_DIR = WATER_DIR / "generated"
UPLOADED_DIR = WATER_DIR / "uploaded"

CANVAS = (512, 512)
BG = (244, 246, 249)

WATER_BLUE = (120, 190, 235)
WATER_EDGE = (255, 255, 255)
COFFEE = (96, 60, 33)
GLASS_OUTLINE = (96, 104, 120)
OPAQUE_GRAY = (150, 155, 162)
SKIN = (232, 190, 156)
SKIN_EDGE = (196, 150, 118)
DISPENSER_BODY = (210, 214, 220)
DISPENSER_EDGE = (120, 126, 136)
CAP_BLUE = (60, 120, 190)
TEXT_COLOR = (60, 66, 78)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", CANVAS, BG)
    return img, ImageDraw.Draw(img)


def _caption(draw: ImageDraw.ImageDraw, text: str) -> None:
    font = _font(20)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((CANVAS[0] - w) / 2, CANVAS[1] - 42), text, fill=TEXT_COLOR, font=font)


def _watermark(draw: ImageDraw.ImageDraw, text: str = "PLACEHOLDER") -> None:
    font = _font(16)
    draw.text((10, 10), text, fill=(200, 90, 90), font=font)


def draw_cup(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill_ratio: float,
    liquid_color: tuple[int, int, int] = WATER_BLUE,
    outline: tuple[int, int, int] = GLASS_OUTLINE,
) -> None:
    """Draw a slightly tapered transparent cup, filled `fill_ratio` (0..1) with liquid."""
    x0, y0, x1, y1 = box
    height = y1 - y0
    taper = (x1 - x0) * 0.12  # narrower at the bottom

    def edges_at(y: float) -> tuple[float, float]:
        t = (y - y0) / height
        return x0 + taper * t, x1 - taper * t

    if fill_ratio > 0:
        wy = y0 + (1 - fill_ratio) * height
        lx, rx = edges_at(wy)
        blx, brx = edges_at(y1)
        draw.polygon([(lx, wy), (rx, wy), (brx, y1), (blx, y1)], fill=liquid_color)
        draw.line([(lx, wy), (rx, wy)], fill=WATER_EDGE, width=3)

    blx, brx = edges_at(y1)
    body = [(x0, y0), (x1, y0), (brx, y1), (blx, y1)]
    draw.line(body + [body[0]], fill=outline, width=4)


def draw_hand(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Draw a simple hand wrapping the lower part of a cup at `box`."""
    x0, y0, x1, y1 = box
    palm_top = y0 + (y1 - y0) * 0.45
    draw.rounded_rectangle(
        [x0 - 26, palm_top, x1 + 26, y1 + 26], radius=26, fill=SKIN, outline=SKIN_EDGE, width=3
    )
    finger_w = (x1 - x0 + 44) / 4
    for i in range(4):
        fx = x0 - 22 + i * finger_w
        draw.rounded_rectangle(
            [fx, palm_top - 18, fx + finger_w - 8, palm_top + 40],
            radius=12,
            fill=SKIN,
            outline=SKIN_EDGE,
            width=2,
        )


def draw_bottle(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill_ratio: float,
    *,
    sealed: bool,
    opaque: bool,
) -> None:
    """Draw a bottle. opaque=True hides the contents (can't confirm water)."""
    x0, y0, x1, y1 = box
    cap_h = 30
    neck_w = (x1 - x0) * 0.4
    cx = (x0 + x1) / 2
    # cap
    draw.rectangle([cx - neck_w / 2, y0, cx + neck_w / 2, y0 + cap_h], fill=CAP_BLUE)
    # neck
    draw.rectangle([cx - neck_w / 2, y0 + cap_h, cx + neck_w / 2, y0 + cap_h + 22], fill=(225, 230, 236))
    body_top = y0 + cap_h + 22
    if opaque:
        draw.rounded_rectangle([x0, body_top, x1, y1], radius=18, fill=OPAQUE_GRAY, outline=DISPENSER_EDGE, width=4)
    else:
        if fill_ratio > 0:
            wy = y1 - fill_ratio * (y1 - body_top)
            draw.rounded_rectangle([x0 + 3, wy, x1 - 3, y1], radius=16, fill=WATER_BLUE)
            draw.line([(x0 + 3, wy), (x1 - 3, wy)], fill=WATER_EDGE, width=3)
        draw.rounded_rectangle([x0, body_top, x1, y1], radius=18, outline=GLASS_OUTLINE, width=4)
    if sealed:
        draw.text((x0, y1 + 4), "sealed", fill=TEXT_COLOR, font=_font(14))


def draw_dispenser_filling(draw: ImageDraw.ImageDraw) -> None:
    """Draw a water dispenser pouring a stream into a cup below the spout."""
    # dispenser body
    draw.rounded_rectangle([120, 60, 392, 250], radius=18, fill=DISPENSER_BODY, outline=DISPENSER_EDGE, width=4)
    # top water tank hint
    draw.rounded_rectangle([190, 20, 322, 70], radius=14, fill=(180, 210, 235), outline=DISPENSER_EDGE, width=3)
    # spout
    draw.rectangle([246, 250, 266, 285], fill=DISPENSER_EDGE)
    # cup under spout
    cup_box = (216, 340, 296, 452)
    # water stream from spout into cup
    draw.rectangle([250, 285, 262, 352], fill=WATER_BLUE)
    draw_cup(draw, cup_box, fill_ratio=0.4)


# ---------------------------------------------------------------------------
# Scene renderers keyed by name
# ---------------------------------------------------------------------------

def render_full_glass(draw):
    draw_cup(draw, (206, 150, 306, 400), fill_ratio=0.9)
    _caption(draw, "full glass of water")


def render_half_glass(draw):
    draw_cup(draw, (206, 150, 306, 400), fill_ratio=0.5)
    _caption(draw, "half glass of water")


def render_hand_holding_water(draw):
    box = (206, 150, 306, 400)
    draw_cup(draw, box, fill_ratio=0.8)
    draw_hand(draw, box)
    _caption(draw, "hand holding a glass of water")


def render_dispenser_filling(draw):
    draw_dispenser_filling(draw)
    _caption(draw, "water dispenser filling a cup")


def render_water_bottle(draw):
    draw_bottle(draw, (216, 120, 296, 430), fill_ratio=0.85, sealed=False, opaque=False)
    _caption(draw, "transparent bottle with water")


def render_empty_glass(draw):
    draw_cup(draw, (206, 150, 306, 400), fill_ratio=0.0)
    _caption(draw, "empty glass")


def render_nearly_empty_glass(draw):
    draw_cup(draw, (206, 150, 306, 400), fill_ratio=0.06)
    _caption(draw, "nearly empty glass")


def render_coffee_cup(draw):
    draw_cup(draw, (206, 150, 306, 400), fill_ratio=0.8, liquid_color=COFFEE)
    _caption(draw, "cup of coffee (colored beverage)")


def render_closed_bottle(draw):
    draw_bottle(draw, (216, 120, 296, 430), fill_ratio=0.0, sealed=True, opaque=True)
    _caption(draw, "closed opaque bottle, no context")


def render_many_empty_cups(draw):
    for cx in (120, 256, 392):
        draw_cup(draw, (cx - 45, 190, cx + 45, 380), fill_ratio=0.0)
    _caption(draw, "several empty cups")


# name -> renderer
SCENES = {
    "full_glass": render_full_glass,
    "half_glass": render_half_glass,
    "hand_holding_water": render_hand_holding_water,
    "dispenser_filling": render_dispenser_filling,
    "water_bottle": render_water_bottle,
    "empty_glass": render_empty_glass,
    "nearly_empty_glass": render_nearly_empty_glass,
    "coffee_cup": render_coffee_cup,
    "closed_bottle": render_closed_bottle,
    "many_empty_cups": render_many_empty_cups,
    # extra scenes reused for uploaded placeholders
    "two_empty_cups": lambda d: (
        [draw_cup(d, (156 - 45, 190, 156 + 45, 380), 0.0), draw_cup(d, (356 - 45, 190, 356 + 45, 380), 0.0)],
        _caption(d, "two empty cups"),
    ),
}

# 요구된 generated/ 10장: (filename, scene)
GENERATED = [
    ("generated_water_01_full_glass.png", "full_glass"),
    ("generated_water_02_half_glass.png", "half_glass"),
    ("generated_water_03_hand_holding_water.png", "hand_holding_water"),
    ("generated_water_04_dispenser_filling_cup.png", "dispenser_filling"),
    ("generated_water_05_water_bottle.png", "water_bottle"),
    ("generated_water_06_empty_glass.png", "empty_glass"),
    ("generated_water_07_nearly_empty_glass.png", "nearly_empty_glass"),
    ("generated_water_08_coffee_cup.png", "coffee_cup"),
    ("generated_water_09_closed_bottle_no_context.png", "closed_bottle"),
    ("generated_water_10_many_empty_cups.png", "many_empty_cups"),
]

# uploaded/ 8장 placeholder: (filename, scene)
UPLOADED_PLACEHOLDERS = [
    ("water_test_01.png", "hand_holding_water"),
    ("water_test_02.png", "full_glass"),
    ("water_test_03.png", "nearly_empty_glass"),
    ("water_test_04.png", "two_empty_cups"),
    ("water_test_05.png", "hand_holding_water"),
    ("water_test_06.png", "dispenser_filling"),
    ("water_test_07.png", "dispenser_filling"),
    ("water_test_08.png", "dispenser_filling"),
]


def _render(filename: str, scene: str, out_dir: Path, watermark: bool) -> Path:
    img, draw = _new_canvas()
    SCENES[scene](draw)
    if watermark:
        _watermark(draw)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    img.save(out_path)
    return out_path


def generate_generated() -> list[Path]:
    paths = [_render(name, scene, GENERATED_DIR, watermark=False) for name, scene in GENERATED]
    for p in paths:
        print(f"[generated] {p.relative_to(ROOT)}")
    return paths


def generate_uploaded_placeholders() -> list[Path]:
    """Fill empty uploaded/ slots with placeholders.

    NEVER overwrites an existing file: uploaded/ holds the user's real photos, so a
    slot that already has an image (real or previously generated) is left untouched.
    """
    paths: list[Path] = []
    for name, scene in UPLOADED_PLACEHOLDERS:
        target = UPLOADED_DIR / name
        if target.exists():
            print(f"[uploaded-skip] {target.relative_to(ROOT)} already exists (real photo?), not overwriting")
            continue
        paths.append(_render(name, scene, UPLOADED_DIR, watermark=True))
    for p in paths:
        print(f"[uploaded-placeholder] {p.relative_to(ROOT)}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uploaded-placeholders",
        action="store_true",
        help="uploaded/ 슬롯 8장 placeholder도 함께 생성 (실제 사진이 없을 때 파이프라인 검증용)",
    )
    args = parser.parse_args()

    generated = generate_generated()
    uploaded = generate_uploaded_placeholders() if args.uploaded_placeholders else []
    print(f"\n[done] generated={len(generated)} uploaded_placeholders={len(uploaded)}")


if __name__ == "__main__":
    main()
