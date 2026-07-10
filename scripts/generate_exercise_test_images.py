"""Synthetic exercise-verification test-image generator.

물 인증(generate_water_test_images.py)과 동일한 구조. Qwen2.5-VL-3B 기반 운동 인증
파이프라인(VLM 증거 추출 → normalize_exercise_output → Rule Engine)과 PASS/FAIL 판정
로직을 비용 없이 검증하기 위한 합성 이미지를 만든다.

MVP 1차 범위: gym + home_workout (수영/요가/필라테스/러닝은 다음 단계).

실제 사진 생성 API 없이 PIL 도형만으로 헬스장 기구/홈트 매트/사무실/침실/음식 등의 상황을
시각적으로 구분되게 그린다. 픽셀 자체를 실제 VLM으로 판독하는 것이 목적이 아니라,
사람이 봐도 구분되고 라벨/매니페스트와 1:1 대응되는 픽스처를 확보하는 것이 목표다.

사용법:
    python scripts/generate_exercise_test_images.py

출력:
    data/test_images/exercise/generated/generated_exercise_01_gym_dumbbell.png ... _12_...png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "data" / "test_images" / "exercise" / "generated"

CANVAS = (512, 512)
BG = (244, 246, 249)
FLOOR = (223, 227, 233)
DARK = (70, 76, 88)
METAL = (120, 126, 138)
MAT = (90, 160, 210)
BAND = (210, 120, 60)
SKIN = (232, 190, 156)
TEXT_COLOR = (60, 66, 78)
WOOD = (200, 170, 130)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", CANVAS, BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 360, CANVAS[0], CANVAS[1]], fill=FLOOR)  # 바닥
    return img, d


def _caption(d: ImageDraw.ImageDraw, text: str) -> None:
    font = _font(20)
    bbox = d.textbbox((0, 0), text, font=font)
    d.text(((CANVAS[0] - (bbox[2] - bbox[0])) / 2, CANVAS[1] - 40), text, fill=TEXT_COLOR, font=font)


def _dumbbell(d, cx, cy, scale=1.0):
    w = int(120 * scale)
    d.rectangle([cx - w // 2, cy - 8, cx + w // 2, cy + 8], fill=METAL)
    for sx in (cx - w // 2, cx + w // 2):
        d.ellipse([sx - 22, cy - 34, sx + 22, cy + 34], fill=DARK)


def draw_gym_dumbbell(d):
    _dumbbell(d, 256, 300, 1.2)
    _dumbbell(d, 150, 330, 0.7)
    d.rectangle([40, 120, 120, 360], outline=METAL, width=3)  # rack hint
    _caption(d, "gym: dumbbells on a rack")


def draw_treadmill(d):
    d.polygon([(150, 340), (360, 340), (390, 250), (300, 250)], fill=DARK)  # belt
    d.rectangle([300, 150, 330, 260], fill=METAL)  # console arm
    d.rectangle([290, 120, 360, 160], fill=(150, 156, 168))  # console
    _caption(d, "gym: treadmill")


def draw_weight_bench(d):
    d.rectangle([160, 300, 360, 320], fill=DARK)  # bench pad
    for lx in (175, 340):
        d.rectangle([lx, 320, lx + 12, 360], fill=METAL)  # legs
    d.rectangle([120, 200, 132, 320], fill=METAL)  # upright
    d.rectangle([90, 205, 300, 215], fill=METAL)  # barbell
    for sx in (95, 290):
        d.ellipse([sx - 14, 185, sx + 14, 235], fill=DARK)
    _caption(d, "gym: weight bench + barbell")


def draw_yoga_mat_home(d):
    d.rounded_rectangle([120, 330, 400, 400], radius=16, fill=MAT)
    d.rectangle([0, 90, CANVAS[0], 110], fill=(210, 214, 220))  # baseboard/home hint
    _caption(d, "home workout: exercise mat")


def draw_resistance_band(d):
    d.arc([150, 250, 360, 400], start=200, end=520, fill=BAND, width=14)  # band
    d.ellipse([150, 300, 190, 360], outline=BAND, width=10)  # handle loop
    d.ellipse([330, 300, 370, 360], outline=BAND, width=10)
    _caption(d, "home workout: resistance band")


def _stick_figure(d, cx, cy, pose="squat"):
    d.ellipse([cx - 18, cy - 90, cx + 18, cy - 54], fill=SKIN)  # head
    d.line([(cx, cy - 54), (cx, cy - 4)], fill=DARK, width=8)   # torso
    if pose == "squat":
        d.line([(cx, cy - 4), (cx - 30, cy + 20)], fill=DARK, width=8)
        d.line([(cx - 30, cy + 20), (cx - 30, cy + 60)], fill=DARK, width=8)
        d.line([(cx, cy - 4), (cx + 30, cy + 20)], fill=DARK, width=8)
        d.line([(cx + 30, cy + 20), (cx + 30, cy + 60)], fill=DARK, width=8)
        d.line([(cx, cy - 40), (cx - 40, cy - 50)], fill=DARK, width=8)  # arms out
        d.line([(cx, cy - 40), (cx + 40, cy - 50)], fill=DARK, width=8)


def draw_person_workout_pose(d):
    d.rounded_rectangle([120, 360, 400, 400], radius=12, fill=MAT)  # mat under
    _stick_figure(d, 256, 320, "squat")
    _caption(d, "home workout: person exercising")


def draw_office_desk(d):
    d.rectangle([100, 300, 420, 320], fill=WOOD)  # desk top
    for lx in (110, 400):
        d.rectangle([lx, 320, lx + 12, 360], fill=WOOD)
    d.rectangle([210, 250, 300, 305], fill=DARK)  # laptop screen
    d.polygon([(200, 305), (310, 305), (320, 320), (190, 320)], fill=(150, 156, 168))  # keyboard
    _caption(d, "office desk with a laptop")


def draw_bedroom(d):
    d.rectangle([90, 280, 400, 360], fill=(180, 150, 170))  # bed
    d.rectangle([90, 250, 180, 300], fill=(240, 240, 245))  # pillow
    d.rectangle([70, 250, 90, 360], fill=WOOD)  # headboard
    _caption(d, "bedroom, no exercise")


def draw_food_table(d):
    d.rectangle([60, 330, 452, 360], fill=WOOD)
    d.ellipse([180, 300, 330, 350], fill=(250, 250, 250))  # plate
    d.ellipse([215, 305, 295, 340], fill=(210, 120, 90))  # food
    d.ellipse([120, 315, 165, 345], fill=(120, 180, 220))  # cup
    _caption(d, "food on a dining table")


def draw_empty_room(d):
    d.line([(0, 200), (CANVAS[0], 200)], fill=(210, 214, 220), width=3)  # wall/floor edge
    d.line([(120, 360), (60, 460)], fill=(210, 214, 220), width=2)
    d.line([(392, 360), (452, 460)], fill=(210, 214, 220), width=2)
    _caption(d, "empty room, no equipment")


def draw_shoes_only(d):
    for cx in (190, 320):
        d.ellipse([cx - 55, 320, cx + 55, 356], fill=DARK)  # sole
        d.pieslice([cx - 55, 288, cx + 40, 356], start=180, end=360, fill=(150, 156, 168))  # upper
    _caption(d, "running shoes only")


def draw_water_bottle_only(d):
    cx = 256
    d.rectangle([cx - 12, 200, cx + 12, 224], fill=(60, 120, 190))  # cap
    d.rounded_rectangle([cx - 34, 224, cx + 34, 360], radius=18, fill=(150, 200, 235), outline=METAL, width=3)
    _caption(d, "water bottle only")


SCENES = {
    "gym_dumbbell": draw_gym_dumbbell,
    "treadmill_gym": draw_treadmill,
    "weight_bench": draw_weight_bench,
    "yoga_mat_home": draw_yoga_mat_home,
    "resistance_band_home": draw_resistance_band,
    "person_workout_pose": draw_person_workout_pose,
    "office_desk": draw_office_desk,
    "bedroom_no_exercise": draw_bedroom,
    "food_table": draw_food_table,
    "empty_room": draw_empty_room,
    "shoes_only": draw_shoes_only,
    "water_bottle_only": draw_water_bottle_only,
}

GENERATED = [
    ("generated_exercise_01_gym_dumbbell.png", "gym_dumbbell"),
    ("generated_exercise_02_treadmill_gym.png", "treadmill_gym"),
    ("generated_exercise_03_weight_bench.png", "weight_bench"),
    ("generated_exercise_04_yoga_mat_home.png", "yoga_mat_home"),
    ("generated_exercise_05_resistance_band_home.png", "resistance_band_home"),
    ("generated_exercise_06_person_workout_pose.png", "person_workout_pose"),
    ("generated_exercise_07_office_desk.png", "office_desk"),
    ("generated_exercise_08_bedroom_no_exercise.png", "bedroom_no_exercise"),
    ("generated_exercise_09_food_table.png", "food_table"),
    ("generated_exercise_10_empty_room.png", "empty_room"),
    ("generated_exercise_11_shoes_only.png", "shoes_only"),
    ("generated_exercise_12_water_bottle_only.png", "water_bottle_only"),
]


def main() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    for name, scene in GENERATED:
        img, d = _canvas()
        SCENES[scene](d)
        out = GENERATED_DIR / name
        img.save(out)
        print(f"[generated] {out.relative_to(ROOT)}")
    print(f"\n[done] generated={len(GENERATED)}")


if __name__ == "__main__":
    main()
