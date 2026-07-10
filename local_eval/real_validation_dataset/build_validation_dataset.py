"""real_validation_dataset 구축 스크립트 (이미지 배치 + annotation manifest 생성).

동작(GPU 불필요 — 파일 복사 + PIL 합성만):
1) 기존 검증용 실제 이미지(water/exercise/study manifest)를 images/{type}/{pass|fail}/ 로 복사.
2) 사용자가 지정한 목표 구성(water 20 / exercise 15 / study 15)을 채우기 위해 부족한 카테고리를
   합성 이미지(PIL)로 보충. 합성 이미지는 placeholder 이며, 실제 촬영본으로 교체/증강 권장.
3) annotations/validation_manifest.json 작성.
   각 항목: image / verification_type / ground_truth(PASS|FAIL|BORDERLINE) / expected_evidence /
            description / exercise_activity_type / source(real|synthetic) / difficulty /
            reference_vision_analysis(= --simulate 평가에 사용하는 참조 VisionAnalysis)

기존 파일/구조(모델 adapter, local_eval metrics, backend API/Rule Engine)는 건드리지 않는다.
이 스크립트는 real_validation_dataset 폴더 안만 채운다.

실행:
    python local_eval/real_validation_dataset/build_validation_dataset.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
IMAGES_DIR = THIS_DIR / "images"
MANIFEST = THIS_DIR / "annotations" / "validation_manifest.json"

WATER_MANIFEST = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
EXERCISE_MANIFEST = ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json"
STUDY_GT = ROOT / "local_eval" / "study_verification_fixture_pack" / "study_ground_truth.jsonl"
STUDY_PACK = ROOT / "local_eval" / "study_verification_fixture_pack"

_LABEL_FROM_DECISION = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE"}


def _folder(ground_truth: str) -> str:
    """PASS → pass/, 그 외(FAIL/BORDERLINE) → fail/. ground_truth 는 manifest 에 그대로 보존."""
    return "pass" if ground_truth == "PASS" else "fail"


def _empty_analysis() -> dict:
    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None, "objects": [], "visible_text": [], "visual_evidence": [],
        "study_visual_evidence": [], "water_visual_evidence": [], "exercise_visual_evidence": [],
    }


# ---------------------------------------------------------------------------
# 1) 기존 실제 이미지 수집
# ---------------------------------------------------------------------------

def _collect_water() -> list[dict]:
    data = json.loads(WATER_MANIFEST.read_text(encoding="utf-8"))["images"]
    out = []
    for i, e in enumerate(data, 1):
        gt = e["expected_label"]
        va = e.get("vision_analysis") or _empty_analysis()
        out.append({
            "src": ROOT / e["image_path"],
            "verification_type": "water",
            "ground_truth": gt,
            "expected_evidence": list(va.get("water_visual_evidence", [])),
            "description": e.get("reason", ""),
            "exercise_activity_type": None,
            "source": "real",
            "difficulty": e.get("difficulty", "unknown"),
            "reference_vision_analysis": va,
            "_name": f"water_real_{i:02d}",
        })
    return out


def _collect_exercise() -> list[dict]:
    data = json.loads(EXERCISE_MANIFEST.read_text(encoding="utf-8"))["images"]
    out = []
    for i, e in enumerate(data, 1):
        gt = e["expected_label"]
        va = e.get("vision_analysis") or _empty_analysis()
        out.append({
            "src": ROOT / e["image_path"],
            "verification_type": "exercise",
            "ground_truth": gt,
            "expected_evidence": list(va.get("exercise_visual_evidence", [])),
            "description": e.get("reason", ""),
            "exercise_activity_type": e.get("exercise_activity_type"),
            "source": "real",
            "difficulty": e.get("difficulty", "unknown"),
            "reference_vision_analysis": va,
            "_name": f"exercise_real_{i:02d}",
        })
    return out


def _collect_study() -> list[dict]:
    out = []
    for i, line in enumerate((STUDY_GT.read_text(encoding="utf-8")).splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        gt_rec = json.loads(line)
        gt = _LABEL_FROM_DECISION.get(gt_rec.get("expected_decision"), "FAIL")
        study_ev = list(gt_rec.get("expected_study_evidence", []))
        objs = [{"label": o, "confidence": 0.9, "evidence": None}
                for o in gt_rec.get("expected_objects", [])]
        va = _empty_analysis()
        va["objects"] = objs
        va["study_visual_evidence"] = study_ev
        img_rel = gt_rec.get("image_path", f"images/{gt_rec['image_id']}.png")
        out.append({
            "src": STUDY_PACK / img_rel,
            "verification_type": "study",
            "ground_truth": gt,
            "expected_evidence": study_ev,
            "description": gt_rec.get("notes", ""),
            "exercise_activity_type": None,
            "source": "real",
            "difficulty": "unknown",
            "reference_vision_analysis": va,
            "_name": f"study_real_{i:02d}",
        })
    return out


# ---------------------------------------------------------------------------
# 2) 합성 보충 이미지 (부족 카테고리 커버; placeholder)
# ---------------------------------------------------------------------------

def _synth_specs() -> list[dict]:
    """목표 구성 보충용 합성 이미지 스펙. 실제 촬영본으로 교체 권장."""
    def wa(**kw):  # water analysis helper
        a = _empty_analysis(); a.update(kw); return a
    specs = [
        # --- water 보충 (FAIL 다양화) ---
        {"verification_type": "water", "ground_truth": "FAIL", "activity": None,
         "caption": "closed opaque bottle", "color": (120, 120, 120),
         "description": "닫힌 불투명 물병 — 물 여부 확인 불가",
         "evidence": ["opaque_closed_container"],
         "va": wa(water_visual_evidence=["opaque_closed_container"], scene="closed_bottle")},
        {"verification_type": "water", "ground_truth": "FAIL", "activity": None,
         "caption": "energy drink can", "color": (200, 60, 60),
         "description": "색이 있는 캔 음료 — 물 아님",
         "evidence": ["non_water_beverage"],
         "va": wa(water_visual_evidence=["non_water_beverage"], scene="beverage_can")},
        # --- exercise 보충 ---
        {"verification_type": "exercise", "ground_truth": "PASS", "activity": "gym",
         "caption": "barbell rack in gym", "color": (60, 60, 90),
         "description": "헬스장 바벨 랙",
         "evidence": ["gym_environment", "barbell_present"],
         "va": wa(exercise_visual_evidence=["gym_environment", "barbell_present"], scene="gym")},
        {"verification_type": "exercise", "ground_truth": "PASS", "activity": "gym",
         "caption": "weight machine", "color": (70, 80, 100),
         "description": "웨이트 머신",
         "evidence": ["gym_environment", "weight_machine_present"],
         "va": wa(exercise_visual_evidence=["gym_environment", "weight_machine_present"], scene="gym")},
        {"verification_type": "exercise", "ground_truth": "FAIL", "activity": "gym",
         "caption": "office desk with monitor", "color": (150, 150, 160),
         "description": "사무실 책상 — 운동 환경 아님",
         "evidence": ["unrelated_environment"],
         "va": wa(exercise_visual_evidence=["unrelated_environment"], scene="office")},
        # --- study 보충 (디지털 학습 PASS + 오락 FAIL) ---
        {"verification_type": "study", "ground_truth": "PASS", "activity": None,
         "caption": "PDF document on screen", "color": (240, 240, 240),
         "description": "화면에 PDF 학습 문서",
         "evidence": ["educational_document", "study_content_on_screen"],
         "va": wa(study_visual_evidence=["educational_document", "study_content_on_screen"],
                  objects=[{"label": "laptop", "confidence": 0.9, "evidence": None},
                           {"label": "monitor", "confidence": 0.9, "evidence": None}], scene="screen_study")},
        {"verification_type": "study", "ground_truth": "PASS", "activity": None,
         "caption": "lecture video on laptop", "color": (30, 30, 60),
         "description": "노트북 강의 영상",
         "evidence": ["lecture_video", "study_content_on_screen"],
         "va": wa(study_visual_evidence=["lecture_video", "study_content_on_screen"],
                  objects=[{"label": "laptop", "confidence": 0.9, "evidence": None}], scene="lecture")},
        {"verification_type": "study", "ground_truth": "PASS", "activity": None,
         "caption": "code editor screen", "color": (20, 40, 30),
         "description": "코드 작성 화면",
         "evidence": ["code_editor", "study_content_on_screen"],
         "va": wa(study_visual_evidence=["code_editor", "study_content_on_screen"],
                  objects=[{"label": "laptop", "confidence": 0.9, "evidence": None},
                           {"label": "keyboard", "confidence": 0.9, "evidence": None}], scene="coding")},
        {"verification_type": "study", "ground_truth": "FAIL", "activity": None,
         "caption": "video game screen", "color": (90, 20, 90),
         "description": "게임 화면 — 학습 아님",
         "evidence": ["gaming_content"],
         "va": wa(study_visual_evidence=["gaming_content"],
                  objects=[{"label": "monitor", "confidence": 0.9, "evidence": None}], scene="gaming")},
        {"verification_type": "study", "ground_truth": "FAIL", "activity": None,
         "caption": "social media feed", "color": (40, 120, 200),
         "description": "SNS 피드 — 학습 아님",
         "evidence": ["social_media"],
         "va": wa(study_visual_evidence=["social_media"],
                  objects=[{"label": "tablet", "confidence": 0.9, "evidence": None}], scene="sns")},
    ]
    return specs


def _draw_synth(path: Path, caption: str, color: tuple[int, int, int]) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (512, 512), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([56, 120, 456, 392], fill=color)
    d.rectangle([56, 120, 456, 392], outline=(20, 20, 20), width=4)
    d.text((70, 40), "SYNTHETIC placeholder", fill=(120, 20, 20))
    d.text((70, 430), caption, fill=(20, 20, 20))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _build_synth() -> list[dict]:
    out = []
    counters: dict[str, int] = {}
    for spec in _synth_specs():
        vt = spec["verification_type"]
        counters[vt] = counters.get(vt, 0) + 1
        name = f"{vt}_synth_{counters[vt]:02d}"
        out.append({
            "src": None,  # 합성: 직접 그린다
            "verification_type": vt,
            "ground_truth": spec["ground_truth"],
            "expected_evidence": spec["evidence"],
            "description": spec["description"] + " (합성 placeholder)",
            "exercise_activity_type": spec["activity"],
            "source": "synthetic",
            "difficulty": "synthetic",
            "reference_vision_analysis": spec["va"],
            "_name": name,
            "_caption": spec["caption"],
            "_color": tuple(spec["color"]),
        })
    return out


# ---------------------------------------------------------------------------
# 배치 + manifest 작성
# ---------------------------------------------------------------------------

def main() -> None:
    entries = _collect_water() + _collect_exercise() + _collect_study() + _build_synth()
    manifest_items = []
    for e in entries:
        vt = e["verification_type"]
        folder = _folder(e["ground_truth"])
        suffix = ".png"
        if e["src"] is not None:
            suffix = e["src"].suffix or ".png"
        rel = f"{vt}/{folder}/{e['_name']}{suffix}"
        dst = IMAGES_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if e["src"] is not None:
            if not e["src"].exists():
                print(f"[warn] 원본 없음, 건너뜀: {e['src']}")
                continue
            shutil.copy2(e["src"], dst)
        else:
            _draw_synth(dst, e.get("_caption", ""), e.get("_color", (100, 100, 100)))
        manifest_items.append({
            "image": rel,
            "verification_type": vt,
            "ground_truth": e["ground_truth"],
            "expected_evidence": e["expected_evidence"],
            "description": e["description"],
            "exercise_activity_type": e["exercise_activity_type"],
            "source": e["source"],
            "difficulty": e["difficulty"],
            "reference_vision_analysis": e["reference_vision_analysis"],
        })

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": "real_validation_dataset",
        "note": "물/운동/공부 인증 검증셋. real=기존 검증 이미지, synthetic=placeholder(실촬영 교체 권장).",
        "positive_label": "PASS (=Rule Engine verified). FP 최소화가 최우선.",
        "count": len(manifest_items),
        "images": manifest_items,
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 요약 출력
    from collections import Counter
    by_type = Counter(i["verification_type"] for i in manifest_items)
    by_gt = Counter((i["verification_type"], i["ground_truth"]) for i in manifest_items)
    by_src = Counter(i["source"] for i in manifest_items)
    print(f"[done] {len(manifest_items)} images → {MANIFEST}")
    print(f"  by_type: {dict(by_type)}")
    print(f"  by_source: {dict(by_src)}")
    for vt in ("water", "exercise", "study"):
        row = {gt: by_gt[(vt, gt)] for gt in ("PASS", "FAIL", "BORDERLINE") if by_gt[(vt, gt)]}
        print(f"  {vt}: {row}")


if __name__ == "__main__":
    main()
