"""Qwen 운동 인증 증거 → VisionAnalysis 정규화 (gym + home_workout MVP).

normalize_water_output.py의 운동 버전. Qwen VLM(run_qwen_single.py)이 뽑은 raw evidence를
Rule Engine이 먹을 수 있는 VisionAnalysis 호환 dict로 변환한다. 순수 파이썬만 사용.

보수적 원칙 (false positive < false negative):
- 운동 기구 또는 운동 자세가 명확할 때만 PASS 근거를 만든다.
- 운동화만/물병만 → insufficient_exercise_evidence (근거 부족).
- 사무실/책상/노트북/침실/음식 → unrelated_environment.
- 가정문("if it were a gym", "could be")은 실제 근거로 보지 않는다.
- gym: 기구 근거가 있으면 gym_environment를 보강. home_workout: 매트/밴드/기구/자세가 있으면
  home_workout_environment를 보강. 단, unrelated/insufficient 같은 강한 negative가 있으면 보강하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# ExerciseVisualEvidence enum 중 이 정규화기가 다루는 값 (gym/home MVP + 공통 negative)
EXERCISE_EVIDENCE = {
    "exercise_environment",
    "exercise_equipment_present",
    "exercise_pose_visible",
    "gym_environment",
    "treadmill_present",
    "dumbbell_present",
    "barbell_present",
    "weight_machine_present",
    "exercise_bike_present",
    "gym_bench_present",
    "home_workout_environment",
    "exercise_mat_present",
    "resistance_band_present",
    "home_dumbbell_present",
    "kettlebell_present",
    "pull_up_bar_present",
    "home_exercise_pose_visible",
    "unrelated_environment",
    "wrong_activity_environment",
    "insufficient_exercise_evidence",
    "uncertain_exercise_environment",
}

# exercise allowed_labels (exercise.yaml)
EXERCISE_OBJECT_LABELS = {
    "treadmill", "dumbbell", "barbell", "weight_plate", "weight_machine", "exercise_bike",
    "gym_bench", "locker", "gym_mirror", "stair_climber", "running_shoes", "yoga_mat",
    "exercise_mat", "resistance_band", "kettlebell", "pull_up_bar", "home_interior",
}
EXERCISE_OBJECT_ALIASES = {
    "bench": "gym_bench",
    "weight_bench": "gym_bench",
    "workout_bench": "gym_bench",
    "bench_press": "gym_bench",
    "yoga_mat": "yoga_mat",
    "workout_mat": "exercise_mat",
    "fitness_mat": "exercise_mat",
    "mat": "exercise_mat",
    "exercise_band": "resistance_band",
    "band": "resistance_band",
    "pullup_bar": "pull_up_bar",
    "cable_machine": "weight_machine",
    "spin_bike": "exercise_bike",
    "stationary_bike": "exercise_bike",
    "sneakers": "running_shoes",
    "shoes": "running_shoes",
}

# 긍정 gym/home/pose 구 → evidence 토큰 (부분 문자열, 다중 매핑)
POSITIVE_EX_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    ("gym environment", ("gym_environment",)),
    ("gym ", ("gym_environment",)),
    ("fitness center", ("gym_environment",)),
    ("weight room", ("gym_environment",)),
    ("dumbbell", ("dumbbell_present",)),
    ("treadmill", ("treadmill_present",)),
    ("barbell", ("barbell_present",)),
    ("weight plate", ("barbell_present",)),
    ("weight machine", ("weight_machine_present",)),
    ("cable machine", ("weight_machine_present",)),
    ("lat pulldown", ("weight_machine_present",)),
    ("bench press", ("gym_bench_present",)),
    ("weight bench", ("gym_bench_present",)),
    ("gym bench", ("gym_bench_present",)),
    ("workout bench", ("gym_bench_present",)),
    ("exercise bike", ("exercise_bike_present",)),
    ("stationary bike", ("exercise_bike_present",)),
    # home
    ("home workout", ("home_workout_environment",)),
    ("home gym", ("home_workout_environment",)),
    ("yoga mat", ("exercise_mat_present",)),
    ("exercise mat", ("exercise_mat_present",)),
    ("workout mat", ("exercise_mat_present",)),
    ("fitness mat", ("exercise_mat_present",)),
    ("resistance band", ("resistance_band_present",)),
    ("exercise band", ("resistance_band_present",)),
    ("kettlebell", ("kettlebell_present",)),
    ("pull up bar", ("pull_up_bar_present",)),
    ("pull-up bar", ("pull_up_bar_present",)),
    ("pullup bar", ("pull_up_bar_present",)),
    # pose / activity
    ("workout pose", ("exercise_pose_visible",)),
    ("exercise pose", ("exercise_pose_visible",)),
    ("exercising", ("exercise_pose_visible",)),
    ("person exercising", ("exercise_pose_visible",)),
    ("doing exercise", ("exercise_pose_visible",)),
    ("doing a workout", ("exercise_pose_visible",)),
    ("squat", ("exercise_pose_visible",)),
    ("push up", ("exercise_pose_visible",)),
    ("push-up", ("exercise_pose_visible",)),
    ("pushup", ("exercise_pose_visible",)),
    ("lunge", ("exercise_pose_visible",)),
    ("plank", ("exercise_pose_visible",)),
    ("stretching", ("exercise_pose_visible",)),
    # generic support
    ("exercise equipment", ("exercise_equipment_present",)),
    ("workout equipment", ("exercise_equipment_present",)),
    ("exercise environment", ("exercise_environment",)),
]

# unrelated(사무/침실/음식 등) → unrelated_environment
UNRELATED_PHRASES: tuple[str, ...] = (
    "office", "desk", "laptop", "computer", "workstation", "cubicle",
    "bedroom", "bed ", "pillow", "sleeping",
    "food", "meal", "dining", "plate of", "restaurant", "dinner table", "dining table",
    "kitchen table",
)
# 근거 부족(운동화만/물병만/빈 방) → insufficient_exercise_evidence
INSUFFICIENT_PHRASES: tuple[str, ...] = (
    "shoes only", "only shoes", "just shoes", "running shoes only",
    "water bottle only", "only a water bottle", "just a water bottle",
    "empty room", "no equipment", "no exercise equipment", "nothing related to exercise",
    "no visible exercise",
)
# 불확실 → uncertain_exercise_environment
UNCERTAIN_PHRASES: tuple[str, ...] = (
    "cannot tell if", "unclear if", "not sure if", "hard to tell", "uncertain whether",
)

# 가정/부정문 단서: 실제 negative로 보지 않는다.
HYPOTHETICAL_CUES: tuple[str, ...] = (
    "would indicate", "could indicate", "could be", "could potentially", "if it were",
    "if the", "may be", "might be", "the presence of", "suggests that", "not ",
)

GYM_EQUIPMENT = {
    "dumbbell_present", "treadmill_present", "barbell_present",
    "weight_machine_present", "exercise_bike_present", "gym_bench_present",
}
HOME_EQUIPMENT = {
    "exercise_mat_present", "resistance_band_present", "home_dumbbell_present",
    "kettlebell_present", "pull_up_bar_present",
}


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _canon_object(label: str) -> str | None:
    key = str(label).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    key = EXERCISE_OBJECT_ALIASES.get(key, key)
    return key if key in EXERCISE_OBJECT_LABELS else None


def normalize_objects(raw_objects, confidence):
    result, seen = [], set()
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


def scene_to_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("name", "label", "type", "description"):
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
        return json.dumps(value, ensure_ascii=False) if value else None
    if isinstance(value, list):
        return scene_to_string(value[0]) if value else None
    return None


def resolve_scene(raw):
    return scene_to_string(raw.get("scene")) or scene_to_string(raw.get("scenes"))


def _item_text(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        token = item.get("name") or item.get("label") or item.get("type") or ""
        desc = item.get("description") or item.get("evidence") or ""
        return f"{token} {desc}"
    return str(item)


def _all_text(raw) -> str:
    parts = []
    for key in ("objects", "scenes", "visual_evidence", "negative_evidence", "uncertain_evidence"):
        for item in as_list(raw.get(key)):
            parts.append(_item_text(item))
    if raw.get("scene"):
        parts.append(str(scene_to_string(raw.get("scene")) or ""))
    return " ".join(parts).lower()


def _has_any(text, phrases):
    return any(p in text for p in phrases)


def _match(text, table):
    out = []
    for phrase, tokens in table:
        if phrase in text:
            out.extend(tokens)
    return out


def collect_exercise_evidence(raw: dict, activity_type: str | None = None) -> list[str]:
    """raw → exercise_visual_evidence 토큰 리스트."""
    text = _all_text(raw)

    positives = _match(text, POSITIVE_EX_PHRASES)

    # 강한 negative (가정문 제외)
    unrelated = _has_any(text, UNRELATED_PHRASES) and not _has_any(text, HYPOTHETICAL_CUES)
    uncertain = _has_any(text, UNCERTAIN_PHRASES)

    positives = _dedupe(positives)
    has_equipment = bool((GYM_EQUIPMENT | HOME_EQUIPMENT).intersection(positives))
    has_pose = "exercise_pose_visible" in positives
    has_env = bool({"gym_environment", "home_workout_environment", "exercise_environment"}.intersection(positives))

    # insufficient: 운동화/물병/빈 방 등 + 실제 운동 근거(기구/자세/환경)가 없을 때만
    insufficient = _has_any(text, INSUFFICIENT_PHRASES) and not (has_equipment or has_pose or has_env)

    tokens: list[str] = list(positives)

    # 환경 보강: 기구/자세가 있으면 activity에 맞는 환경을 채워 mandatory를 충족시킨다.
    if activity_type == "gym" and (GYM_EQUIPMENT.intersection(positives)) and "gym_environment" not in tokens:
        tokens.append("gym_environment")
    if activity_type == "home_workout":
        if (HOME_EQUIPMENT.intersection(positives) or has_pose) and "home_workout_environment" not in tokens:
            tokens.append("home_workout_environment")
        if has_pose and "home_exercise_pose_visible" not in tokens:
            tokens.append("home_exercise_pose_visible")

    # 강한 negative는 positive가 없을 때(또는 명백한 unrelated)만 남긴다 → 보수적으로 PASS 차단
    if unrelated and not (has_equipment or has_pose):
        tokens.append("unrelated_environment")
    if insufficient:
        tokens.append("insufficient_exercise_evidence")
    if uncertain and not (has_equipment or has_pose):
        tokens.append("uncertain_exercise_environment")

    # enum 밖의 값은 제거
    return [t for t in _dedupe(tokens) if t in EXERCISE_EVIDENCE]


def normalize_exercise_evidence(raw: dict, activity_type: str | None = None) -> dict:
    """Qwen raw exercise evidence dict → VisionAnalysis 호환 dict."""
    confidence = float(raw.get("confidence", 0.8) or 0.8)
    quality = raw.get("image_quality", {}) or {}
    activity = activity_type or raw.get("activity_type") or raw.get("exercise_activity_type")
    return {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(quality.get("usable", True)),
            "issues": as_list(quality.get("issues")),
        },
        "scene": resolve_scene(raw),
        "objects": normalize_objects(raw.get("objects", []), confidence),
        "visible_text": [str(t) for t in as_list(raw.get("text_observed"))],
        "visual_evidence": [],
        "study_visual_evidence": [],
        "water_visual_evidence": [],
        "exercise_visual_evidence": collect_exercise_evidence(raw, activity),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Qwen exercise evidence to VisionAnalysis JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--activity-type", default=None, choices=["gym", "home_workout"])
    args = parser.parse_args()
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    normalized = normalize_exercise_evidence(raw, args.activity_type)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(normalized, ensure_ascii=False, indent=2))
    print("[INFO] saved:", out)


if __name__ == "__main__":
    main()
