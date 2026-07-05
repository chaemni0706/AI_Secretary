"""Qwen 물 인증 증거 → VisionAnalysis 정규화.

`normalize_qwen_output.py`(study용)의 물 버전. Qwen VLM(run_qwen_single.py)이 뽑은
raw evidence JSON을 Rule Engine이 먹을 수 있는 VisionAnalysis 호환 dict로 변환한다.
torch 등 무거운 의존성 없이 순수 파이썬만 사용하므로 pytest에서 직접 검증할 수 있다.

Qwen raw schema (run_qwen_single.py 참고):
    {
      "verification_type": "water",
      "image_quality": {"usable": true, "issues": []},
      "objects": [...],          # 문자열 또는 {"label"/"type"/"name": ...}
      "scenes": [...],
      "visual_evidence": [...],  # 긍정 근거
      "negative_evidence": [...],# 빈 컵/색 음료 등
      "uncertain_evidence": [...],# 불투명/불확실
      "text_observed": [...],
      "confidence": 0.0
    }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# WaterVisualEvidence enum (image_verification_schema.py와 일치)
WATER_EVIDENCE = {
    "visible_water",
    "visible_clear_liquid",
    "filled_container",
    "sealed_water_bottle",
    "water_stream",
    "container_under_dispenser",
    "receiving_water",
    "empty_container",
    "opaque_closed_container",
    "non_water_beverage",
    "uncertain_liquid",
}

# Qwen이 흔히 내놓는 표현 → 표준 water evidence 별칭
WATER_EVIDENCE_ALIASES = {
    "water": "visible_water",
    "visible_liquid": "visible_clear_liquid",
    "clear_liquid": "visible_clear_liquid",
    "filled": "filled_container",
    "full_container": "filled_container",
    "sealed_bottle": "sealed_water_bottle",
    "pouring_water": "water_stream",
    "receiving": "receiving_water",
    "dispensing_water": "water_stream",
    "empty": "empty_container",
    "empty_cup": "empty_container",
    "colored_beverage": "non_water_beverage",
    "coffee": "non_water_beverage",
    "juice": "non_water_beverage",
    "closed_opaque": "opaque_closed_container",
    "unclear_liquid": "uncertain_liquid",
}

# 물 인증 관련 허용 object label (water.yaml allowed_labels)
WATER_OBJECT_LABELS = {
    "cup",
    "glass",
    "tumbler",
    "water_bottle",
    "pet_bottle",
    "water_container",
    "water_dispenser",
}
WATER_OBJECT_ALIASES = {
    "bottle": "water_bottle",
    "plastic_bottle": "pet_bottle",
    "mug": "cup",
    "pitcher": "water_container",
    "jug": "water_container",
    "dispenser": "water_dispenser",
    "water_purifier": "water_dispenser",
    "purifier": "water_dispenser",
}


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _canon_object(label: str) -> str | None:
    key = str(label).strip().lower().replace(" ", "_")
    key = WATER_OBJECT_ALIASES.get(key, key)
    return key if key in WATER_OBJECT_LABELS else None


def normalize_objects(raw_objects, confidence):
    result = []
    seen = set()
    for obj in as_list(raw_objects):
        if isinstance(obj, str):
            label, evidence = obj, None
        elif isinstance(obj, dict):
            label = obj.get("label") or obj.get("type") or obj.get("name")
            evidence = obj.get("evidence") or obj.get("description")
        else:
            continue
        if not label:
            continue
        canon = _canon_object(label)
        if canon and canon not in seen:
            seen.add(canon)
            result.append({"label": canon, "confidence": float(confidence), "evidence": evidence})
    return result


def _canon_evidence(item: str) -> str | None:
    key = str(item).strip().lower().replace(" ", "_")
    key = WATER_EVIDENCE_ALIASES.get(key, key)
    return key if key in WATER_EVIDENCE else None


def collect_water_evidence(raw: dict) -> list[str]:
    items = []
    items += as_list(raw.get("visual_evidence"))
    items += as_list(raw.get("negative_evidence"))
    items += as_list(raw.get("uncertain_evidence"))
    out, seen = [], set()
    for item in items:
        canon = _canon_evidence(item)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def normalize_water_evidence(raw: dict) -> dict:
    """Qwen raw water evidence dict → VisionAnalysis 호환 dict."""
    confidence = float(raw.get("confidence", 0.8) or 0.8)
    quality = raw.get("image_quality", {}) or {}
    scenes = raw.get("scenes")
    scene = raw.get("scene") or (scenes[0] if isinstance(scenes, list) and scenes else None)

    return {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(quality.get("usable", True)),
            "issues": as_list(quality.get("issues")),
        },
        "scene": scene,
        "objects": normalize_objects(raw.get("objects", []), confidence),
        "visible_text": [str(t) for t in as_list(raw.get("text_observed"))],
        "visual_evidence": [],
        "study_visual_evidence": [],
        "water_visual_evidence": collect_water_evidence(raw),
        "exercise_visual_evidence": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Qwen water evidence to VisionAnalysis JSON.")
    parser.add_argument("--input", required=True, help="Qwen raw evidence JSON path")
    parser.add_argument("--output", required=True, help="Normalized VisionAnalysis JSON path")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    normalized = normalize_water_evidence(raw)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(normalized, ensure_ascii=False, indent=2))
    print("[INFO] saved:", out)


if __name__ == "__main__":
    main()
