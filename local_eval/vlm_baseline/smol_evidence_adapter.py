"""SmolVLM Evidence Adapter → EXISTING Rule Engine.

SmolVLM 의 VisionAnalysis 호환 evidence(기존 스키마 codes)를 그대로 기존 Rule Engine(evaluate_image_verification)에
넣어 local_result 를 얻고, orchestrator 의 fallback 정책이 쓸 local_output(신뢰 신호) 을 유도한다.
**Smol 은 final_result 를 결정하지 않는다.** 최종 판정은 기존 Rule Engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from backend.database.schema.image_verification_schema import (
        VisionAnalysis, ImageVerificationContext,
    )
    from backend.services.image_verification_rule_engine import evaluate_image_verification
    _RE_OK, _RE_ERR = True, ""
except Exception as _exc:  # noqa: BLE001
    _RE_OK, _RE_ERR = False, f"{type(_exc).__name__}: {_exc}"

# task별 blocker(부정) / uncertain 코드 (schema enum 기준). 나머지 코드는 positive 로 간주.
_BLOCKER = {
    "water": {"empty_container", "opaque_closed_container", "non_water_beverage", "sealed_water_bottle"},
    "study": {"gaming_content", "entertainment_video", "social_media", "shopping_content",
              "non_study_screen", "closed_study_materials"},
    "exercise": {"unrelated_environment", "wrong_activity_environment", "insufficient_exercise_evidence"},
}
_UNCERTAIN = {"water": {"uncertain_liquid"}, "study": {"uncertain_screen_content"},
              "exercise": {"uncertain_exercise_environment"}}

_ACT = {  # exercise activity 유도(기존 규칙이 context.exercise_activity_type 요구)
    "gym": {"gym_environment", "treadmill_present", "dumbbell_present", "barbell_present",
            "weight_machine_present", "exercise_bike_present", "gym_bench_present", "exercise_equipment_present"},
    "running": {"running_environment", "running_track_present", "treadmill_running_environment",
                "stadium_track_present", "park_running_path_present"},
    "home_workout": {"home_workout_environment", "exercise_mat_present", "resistance_band_present",
                     "home_dumbbell_present", "kettlebell_present", "pull_up_bar_present", "home_exercise_pose_visible"},
    "yoga": {"yoga_environment", "yoga_mat_present", "yoga_studio_present", "yoga_pose_visible"},
    "pilates": {"pilates_environment", "pilates_reformer_present", "pilates_equipment_present"},
    "swimming": {"swimming_pool_environment", "swimming_lane_present", "lane_rope_present"},
}


def _derive_activity(codes):
    best, sc = "gym", 0
    for a, s in _ACT.items():
        n = len(set(codes) & s)
        if n > sc:
            best, sc = a, n
    return best


def to_local_output(engine_result, task):
    """SmolVLM engine 결과 → 기존 Rule Engine 호출 → local_output(신뢰 신호 포함)."""
    parse_status = engine_result.get("parse_status", "failed")
    engine_error = engine_result.get("engine_error", "")
    va_dict = engine_result.get("va_dict")
    base = {"final_result": "error", "engine_error": engine_error, "parse_status": parse_status,
            "evidence_codes": [], "has_positive": False, "has_blocker": False,
            "uncertainty": "high", "image_quality": "unknown", "mandatory_passed": False,
            "rule_engine_fallback": (not _RE_OK), "rule_reason": "", "rule_trace": []}
    if engine_error or va_dict is None:
        base["final_result"] = "error"
        return base
    codes = list(va_dict.get(f"{task}_visual_evidence", []) or [])
    blockers = [c for c in codes if c in _BLOCKER[task]]
    uncertain = [c for c in codes if c in _UNCERTAIN[task]]
    positives = [c for c in codes if c not in _BLOCKER[task] and c not in _UNCERTAIN[task]]
    usable = bool(((va_dict.get("quality") or {}).get("usable", True)))
    # uncertainty high: 명시적 uncertain 코드가 있거나, 근거가 텅 빔(positive/blocker 둘 다 없음).
    # 명확한 blocker 만 있고 positive 없음 → uncertainty low (깨끗한 거절 근거).
    base.update({"evidence_codes": codes, "has_positive": bool(positives), "has_blocker": bool(blockers),
                 "uncertainty": "high" if (uncertain or (not positives and not blockers)) else "low",
                 "image_quality": "good" if usable else "poor"})
    if not _RE_OK:
        base["final_result"] = "retake_required"
        base["rule_reason"] = f"rule_engine_unavailable({_RE_ERR})"
        return base
    va = VisionAnalysis(**{k: v for k, v in va_dict.items() if not k.startswith("_")})
    ctx = ImageVerificationContext(exercise_activity_type=_derive_activity(codes) if task == "exercise" else None)
    data = evaluate_image_verification(task, va, ctx)
    base.update({"final_result": data.result, "mandatory_passed": data.mandatory_passed,
                 "rule_reason": (data.rule_evidence[0].message if data.rule_evidence else ""),
                 "rule_trace": [e.code for e in data.rule_evidence]})
    return base
