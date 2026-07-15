"""Deterministic rule engine for image verification."""

from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationContext,
    ImageVerificationData,
    RuleEvidence,
    RuleScoreBreakdown,
    VerificationResult,
    VerificationType,
    VisionAnalysis,
)
from backend.services.image_verification_rules_loader import load_rule


def evaluate_image_verification(
    verification_type: VerificationType,
    analysis: VisionAnalysis,
    context: ImageVerificationContext,
) -> ImageVerificationData:
    rule = load_rule(verification_type)
    evidence: list[RuleEvidence] = []
    mandatory_passed = _check_mandatory(rule, analysis, context, evidence)
    breakdown = _score(rule, analysis, context, evidence)
    result = _decide(rule, breakdown.total_score, mandatory_passed, evidence)
    return ImageVerificationData(
        verification_type=verification_type,
        result=result,
        score=breakdown.total_score,
        mandatory_passed=mandatory_passed,
        score_breakdown=breakdown,
        vlm_analysis=analysis,
        rule_evidence=evidence,
    )


def _check_mandatory(
    rule: dict[str, Any],
    analysis: VisionAnalysis,
    context: ImageVerificationContext,
    evidence: list[RuleEvidence],
) -> bool:
    mandatory = rule.get("mandatory", {}) or {}
    passed = True
    labels = _labels(analysis)

    if mandatory.get("quality_usable", False) and not analysis.quality.usable:
        passed = False
        evidence.append(RuleEvidence(code="quality_unusable", message="이미지 품질이 인증에 적합하지 않습니다."))

    if mandatory.get("water_patterns", False):
        _append_water_priority_evidence(analysis, evidence)
    if mandatory.get("study_patterns", False):
        _append_study_priority_evidence(analysis, evidence)
    if mandatory.get("exercise_patterns", False):
        _append_exercise_priority_evidence(analysis, context, evidence)

    min_objects = int(mandatory.get("min_allowed_objects", 0) or 0)
    if min_objects and len(labels) < min_objects:
        passed = False
        evidence.append(RuleEvidence(code="object_missing", message="필수 객체가 충분히 보이지 않습니다."))

    any_of = [label for label in mandatory.get("any_of_objects", []) if isinstance(label, str)]
    if any_of and not labels.intersection(any_of):
        passed = False
        evidence.append(RuleEvidence(code="required_object_missing", message="인증에 필요한 객체가 보이지 않습니다."))

    if mandatory.get("water_patterns", False) and not _water_mandatory_passed(analysis):
        passed = False
        evidence.append(RuleEvidence(code="water_pattern_missing", message="물 인증에 필요한 물/용기 근거가 부족합니다."))
    if mandatory.get("study_patterns", False) and not _study_mandatory_passed(analysis):
        passed = False
        evidence.append(RuleEvidence(code="study_pattern_missing", message="공부 인증에 필요한 학습 자료 또는 학습 콘텐츠 근거가 부족합니다."))
    if mandatory.get("exercise_patterns", False) and not _exercise_mandatory_passed(analysis, context):
        passed = False
        evidence.append(
            RuleEvidence(
                code="exercise_pattern_missing",
                message="선택한 운동과 관련된 장소, 기구 또는 환경 근거가 부족합니다.",
            )
        )

    for group in mandatory.get("required_groups", []) or []:
        code = str(group.get("code") or "required_group_missing")
        group_labels = [label for label in group.get("any_of_objects", []) if isinstance(label, str)]
        text_keywords = [str(k).lower() for k in group.get("any_of_text", [])]
        visual_keywords = [str(k).lower() for k in group.get("any_of_visual_evidence", [])]

        has_label = not group_labels or bool(labels.intersection(group_labels))
        visible_text = " ".join(analysis.visible_text).lower()
        visual_evidence = " ".join(analysis.visual_evidence).lower()
        has_text = not text_keywords or any(k in visible_text for k in text_keywords)
        has_visual = not visual_keywords or any(k in visual_evidence for k in visual_keywords)
        if not (has_label and has_text and has_visual):
            passed = False
            evidence.append(
                RuleEvidence(
                    code=code,
                    message=str(group.get("message") or "필수 인증 근거가 부족합니다."),
                )
            )

    required_time = mandatory.get("requires_scheduled_time", False)
    if required_time and not context.time.scheduled_at:
        passed = False
        evidence.append(RuleEvidence(code="scheduled_time_missing", message="기상 인증에는 예정 시간이 필요합니다."))

    window = mandatory.get("scheduled_time_window_minutes")
    if context.time.scheduled_at and context.time.captured_at and window is not None:
        if not _within_minutes(context.time.captured_at, context.time.scheduled_at, int(window)):
            passed = False
            evidence.append(RuleEvidence(code="outside_time_window", message="촬영 시간이 인증 가능 범위를 벗어났습니다."))

    return passed


def _score(
    rule: dict[str, Any],
    analysis: VisionAnalysis,
    context: ImageVerificationContext,
    evidence: list[RuleEvidence],
) -> RuleScoreBreakdown:
    scoring = rule.get("scoring", {}) or {}
    breakdown = RuleScoreBreakdown(base_score=int(scoring.get("base_score", 0) or 0))

    labels = _labels(analysis)
    object_scores = scoring.get("object_scores", {}) or {}
    for label in labels:
        delta = int(object_scores.get(label, 0) or 0)
        if delta:
            breakdown.object_score += delta
            evidence.append(RuleEvidence(code=f"object:{label}", message=f"{label} 객체가 확인되었습니다.", score_delta=delta))

    for group in scoring.get("similar_object_groups", []) or []:
        names = [name for name in group.get("labels", []) if isinstance(name, str)]
        cap = int(group.get("max_score", 0) or 0)
        if not names or cap <= 0:
            continue
        current = sum(int(object_scores.get(name, 0) or 0) for name in labels.intersection(names))
        if current > cap:
            reduction = current - cap
            breakdown.object_score -= reduction
            evidence.append(RuleEvidence(code="similar_group_cap", message="유사 객체 그룹 최대 점수를 적용했습니다.", score_delta=-reduction))

    water_evidence_scores = scoring.get("water_evidence_scores", {}) or {}
    water_evidence = _water_evidence(analysis)
    visible_liquid = water_evidence.intersection({"visible_water", "visible_clear_liquid"})
    if visible_liquid:
        delta = max(int(water_evidence_scores.get(item, 0) or 0) for item in visible_liquid)
        if delta:
            breakdown.object_score += delta
            evidence.append(RuleEvidence(code="water_evidence:visible_liquid", message="물 또는 투명 액체가 확인되었습니다.", score_delta=delta))
    for item in water_evidence.difference({"visible_water", "visible_clear_liquid"}):
        delta = int(water_evidence_scores.get(item, 0) or 0)
        if delta:
            breakdown.object_score += delta
            evidence.append(RuleEvidence(code=f"water_evidence:{item}", message="물 관련 시각 근거가 확인되었습니다.", score_delta=delta))

    pattern_scores = scoring.get("water_pattern_scores", {}) or {}
    if _has_dispenser_receiving_pattern(analysis):
        delta = int(pattern_scores.get("dispenser_receiving_water", 0) or 0)
        if delta:
            breakdown.object_score += delta
            evidence.append(RuleEvidence(code="water_pattern:dispenser_receiving_water", message="정수기에서 물을 받는 상태가 확인되었습니다.", score_delta=delta))

    study_evidence_scores = scoring.get("study_evidence_scores", {}) or {}
    for item in _study_evidence(analysis):
        delta = int(study_evidence_scores.get(item, 0) or 0)
        if delta:
            breakdown.object_score += delta
            evidence.append(RuleEvidence(code=f"study_evidence:{item}", message="공부 관련 시각 근거가 확인되었습니다.", score_delta=delta))

    if rule.get("mandatory", {}).get("study_patterns", False):
        _score_study_strong_combo(rule, analysis, breakdown, evidence)

    if rule.get("mandatory", {}).get("exercise_patterns", False):
        _score_exercise(rule, analysis, context, breakdown, evidence)

    scene_scores = scoring.get("scene_scores", {}) or {}
    if analysis.scene in scene_scores:
        breakdown.scene_score += int(scene_scores[analysis.scene] or 0)
        evidence.append(RuleEvidence(code=f"scene:{analysis.scene}", message="장면 근거가 확인되었습니다.", score_delta=breakdown.scene_score))

    text_keywords = scoring.get("text_keywords", {}) or {}
    visible_text = " ".join(analysis.visible_text).lower()
    matched_text = set()
    for keyword, points in text_keywords.items():
        key = str(keyword).lower()
        if key and key in visible_text and key not in matched_text:
            delta = int(points or 0)
            breakdown.text_score += delta
            matched_text.add(key)
            evidence.append(RuleEvidence(code=f"text:{keyword}", message=f"문자 근거 '{keyword}'가 확인되었습니다.", score_delta=delta))

    if rule.get("gps", {}).get("enabled", False):
        gps = _gps_score(rule, context)
        if gps:
            breakdown.gps_score = gps
            evidence.append(RuleEvidence(code="gps", message="GPS 보조 점수를 적용했습니다.", score_delta=gps))

    total = (
        breakdown.base_score
        + breakdown.object_score
        + breakdown.scene_score
        + breakdown.text_score
        + breakdown.gps_score
    )
    breakdown.total_score = max(0, min(100, total))
    return breakdown


def _decide(
    rule: dict[str, Any],
    score: int,
    mandatory_passed: bool,
    evidence: list[RuleEvidence],
) -> VerificationResult:
    thresholds = rule.get("thresholds", {}) or {}
    priority_result = _priority_result(evidence)
    if priority_result:
        return priority_result
    if not mandatory_passed:
        if any(item.code == "quality_unusable" for item in evidence):
            return "retake_required"
        return "rejected"
    if score >= int(thresholds.get("verified", 80) or 80):
        return "verified"
    if score >= int(thresholds.get("retake_required", 50) or 50):
        return "retake_required"
    return "rejected"


def _labels(analysis: VisionAnalysis) -> set[str]:
    return {obj.label for obj in analysis.objects}


def _water_evidence(analysis: VisionAnalysis) -> set[str]:
    return set(analysis.water_visual_evidence)


def _study_evidence(analysis: VisionAnalysis) -> set[str]:
    return set(analysis.study_visual_evidence)


def _exercise_evidence(analysis: VisionAnalysis) -> set[str]:
    return set(analysis.exercise_visual_evidence)


def _study_paper_evidence() -> set[str]:
    return {
        "open_textbook",
        "open_workbook",
        "handwritten_notes",
        "highlighted_text",
        "problem_solving_material",
        "educational_document",
    }


def _study_digital_evidence() -> set[str]:
    return {"study_content_on_screen", "lecture_video", "educational_document", "code_editor"}


def _study_strong_positive_evidence() -> set[str]:
    return _study_paper_evidence().union(_study_digital_evidence())


def _study_mandatory_passed(analysis: VisionAnalysis) -> bool:
    """Return True when visible study content is present.

    Policy:
    - Study material/content is mandatory.
    - Devices such as laptop, tablet, monitor, or phone are not enough by themselves.
    - Final verification is still controlled by score thresholds and priority rejection rules.
    """
    labels = _labels(analysis)
    study_evidence = _study_evidence(analysis)

    core_study_content = {
        "open_textbook",
        "open_workbook",
        "handwritten_notes",
        "problem_solving_material",
        "educational_document",
        "study_content_on_screen",
        "lecture_video",
        "code_editor",
    }

    if study_evidence.intersection(core_study_content):
        return True

    # highlighted_text alone can be valid only when a paper study object is also visible.
    paper_objects = {"book", "textbook", "notebook", "workbook", "printed_document"}
    if "highlighted_text" in study_evidence and labels.intersection(paper_objects):
        return True

    return False


def _study_strong_combo_code(analysis: VisionAnalysis) -> str | None:
    """Phase 11.F: explicit strong-positive evidence CO-OCCURRENCES the task
    brief asked to support -- NOT a blanket threshold change. A single weak
    signal (e.g. open_textbook alone, ~25pts) legitimately should not verify;
    but two independent real study signals together are strong enough that
    they should reach `verified` even if their raw point sum falls a little
    short of the configured threshold. Single-evidence images (like the
    known study_002 case: open_textbook + one low-value object = 35pts) are
    deliberately NOT covered here -- that is a genuine single-evidence case,
    not a rule-weight bug (see qwen_recovery/study_reevaluation_notes.md for
    the re-question test that confirmed this)."""
    study_evidence = _study_evidence(analysis)
    combos = [
        ({"open_textbook", "handwritten_notes"}, "textbook_plus_handwritten_notes"),
        ({"open_workbook", "handwritten_notes"}, "workbook_plus_handwritten_notes"),
        ({"open_textbook", "problem_solving_material"}, "textbook_plus_problem_solving"),
        ({"open_workbook", "problem_solving_material"}, "workbook_plus_problem_solving"),
        ({"open_textbook", "educational_document"}, "textbook_plus_educational_document"),
        ({"open_workbook", "educational_document"}, "workbook_plus_educational_document"),
    ]
    for required, code in combos:
        if required.issubset(study_evidence):
            return code
    return None


def _score_study_strong_combo(
    rule: dict[str, Any],
    analysis: VisionAnalysis,
    breakdown: RuleScoreBreakdown,
    evidence: list[RuleEvidence],
) -> None:
    """Mirrors `_score_exercise`'s existing `exercise_mandatory_match` bonus
    pattern (already established in this codebase, not a new mechanism):
    when a named strong-positive combo is present, top up the score to the
    verified threshold -- never below what individual items already scored,
    never above the threshold itself, and never overriding a priority
    rejection (entertainment/social/shopping/non_study_screen are checked
    separately in `_priority_result` and still win regardless)."""
    combo_code = _study_strong_combo_code(analysis)
    if combo_code is None:
        return
    current_study_score = sum(
        item.score_delta for item in evidence
        if (item.code.startswith("study_evidence:") or item.code.startswith("object:")) and item.score_delta > 0
    )
    minimum_score = int(rule.get("thresholds", {}).get("verified", 0) or 0)
    if minimum_score > 0 and current_study_score < minimum_score:
        delta = minimum_score - current_study_score
        breakdown.object_score += delta
        evidence.append(
            RuleEvidence(
                code=f"study_strong_combo:{combo_code}",
                message="복수의 강한 학습 근거 조합이 확인되어 최소 인증 점수를 적용했습니다.",
                score_delta=delta,
            )
        )


def _append_study_priority_evidence(analysis: VisionAnalysis, evidence: list[RuleEvidence]) -> None:
    study_evidence = _study_evidence(analysis)
    rejected_items = {
        "gaming_content": "게임 화면이 확인되어 공부 인증을 거절합니다.",
        "entertainment_video": "오락 영상이 확인되어 공부 인증을 거절합니다.",
        "social_media": "소셜 미디어 화면이 확인되어 공부 인증을 거절합니다.",
        "shopping_content": "쇼핑 화면이 확인되어 공부 인증을 거절합니다.",
        "non_study_screen": "비학습 화면이 확인되어 공부 인증을 거절합니다.",
    }
    for item, message in rejected_items.items():
        if item in study_evidence:
            evidence.append(RuleEvidence(code=f"study_priority:{item}", message=message))
    if (
        "uncertain_screen_content" in study_evidence
        and not study_evidence.intersection(_study_strong_positive_evidence())
    ):
        evidence.append(RuleEvidence(code="study_priority:uncertain_screen_content", message="화면 내용이 공부인지 확실하지 않습니다."))


def _water_container_labels() -> set[str]:
    return {"cup", "glass", "tumbler", "water_bottle", "pet_bottle", "water_container"}


def _has_water_container(analysis: VisionAnalysis) -> bool:
    return bool(_labels(analysis).intersection(_water_container_labels()))


def _water_mandatory_passed(analysis: VisionAnalysis) -> bool:
    water_evidence = _water_evidence(analysis)
    pattern_a = (
        _has_water_container(analysis)
        and bool(water_evidence.intersection({"visible_water", "visible_clear_liquid"}))
        and "filled_container" in water_evidence
    )
    pattern_b = "sealed_water_bottle" in water_evidence
    pattern_c = _has_dispenser_receiving_pattern(analysis)
    return pattern_a or pattern_b or pattern_c


def _has_dispenser_receiving_pattern(analysis: VisionAnalysis) -> bool:
    water_evidence = _water_evidence(analysis)
    return (
        "water_dispenser" in _labels(analysis)
        and _has_water_container(analysis)
        and bool(water_evidence.intersection({"water_stream", "receiving_water"}))
    )


def _append_water_priority_evidence(analysis: VisionAnalysis, evidence: list[RuleEvidence]) -> None:
    water_evidence = _water_evidence(analysis)
    priority_messages = {
        "empty_container": ("water_priority:empty_container", "빈 용기가 확인되어 물 인증을 거절합니다."),
        "non_water_beverage": ("water_priority:non_water_beverage", "물이 아닌 음료가 확인되어 물 인증을 거절합니다."),
        "opaque_closed_container": ("water_priority:opaque_closed_container", "닫힌 불투명 용기는 물 여부를 확인할 수 없습니다."),
        "uncertain_liquid": ("water_priority:uncertain_liquid", "액체가 물인지 확실하지 않습니다."),
    }
    for item, (code, message) in priority_messages.items():
        if item in water_evidence:
            evidence.append(RuleEvidence(code=code, message=message))


_EXERCISE_REQUIRED: dict[ExerciseActivityType, list[set[str]]] = {
    "gym": [
        {"gym_environment"},
        {
            "treadmill_present",
            "dumbbell_present",
            "barbell_present",
            "weight_machine_present",
            "exercise_bike_present",
            "gym_bench_present",
        },
    ],
    "running": [
        {
            "running_track_present",
            "treadmill_running_environment",
            "stadium_track_present",
            "park_running_path_present",
        }
    ],
    "swimming": [
        {"swimming_pool_environment"},
        {"swimming_lane_present", "lane_rope_present", "swim_cap_present", "swim_goggles_present"},
    ],
    "yoga": [
        {"yoga_studio_present", "yoga_pose_visible"},
        {"yoga_environment", "yoga_mat_present"},
    ],
    "pilates": [
        {"pilates_reformer_present", "pilates_equipment_present", "pilates_studio_present"},
    ],
    "home_workout": [
        {
            "exercise_mat_present",
            "resistance_band_present",
            "home_dumbbell_present",
            "kettlebell_present",
            "pull_up_bar_present",
            "home_exercise_pose_visible",
        }
    ],
}

_EXERCISE_ACTIVITY_EVIDENCE: dict[ExerciseActivityType, set[str]] = {
    "gym": {
        "gym_environment",
        "treadmill_present",
        "dumbbell_present",
        "barbell_present",
        "weight_machine_present",
        "exercise_bike_present",
        "gym_bench_present",
    },
    "running": {
        "running_environment",
        "running_track_present",
        "treadmill_running_environment",
        "stadium_track_present",
        "park_running_path_present",
    },
    "swimming": {
        "swimming_pool_environment",
        "swimming_lane_present",
        "lane_rope_present",
        "swim_cap_present",
        "swim_goggles_present",
    },
    "yoga": {"yoga_environment", "yoga_mat_present", "yoga_studio_present", "yoga_pose_visible"},
    "pilates": {
        "pilates_environment",
        "pilates_reformer_present",
        "pilates_equipment_present",
        "pilates_studio_present",
        "pilates_pose_visible",
    },
    "home_workout": {
        "home_workout_environment",
        "exercise_mat_present",
        "resistance_band_present",
        "home_dumbbell_present",
        "kettlebell_present",
        "pull_up_bar_present",
        "home_exercise_pose_visible",
    },
}

_EXERCISE_STRONG_ENVIRONMENT: dict[ExerciseActivityType, set[str]] = {
    "gym": {"gym_environment"},
    "running": {
        "running_environment",
        "running_track_present",
        "treadmill_running_environment",
        "stadium_track_present",
        "park_running_path_present",
    },
    "swimming": {"swimming_pool_environment"},
    "yoga": {"yoga_environment", "yoga_studio_present"},
    "pilates": {"pilates_environment", "pilates_studio_present"},
    "home_workout": {"home_workout_environment"},
}

_EXERCISE_CORE_EQUIPMENT: dict[ExerciseActivityType, set[str]] = {
    "gym": {
        "treadmill_present",
        "dumbbell_present",
        "barbell_present",
        "weight_machine_present",
        "exercise_bike_present",
        "gym_bench_present",
    },
    "running": {
        "running_track_present",
        "treadmill_running_environment",
        "stadium_track_present",
        "park_running_path_present",
    },
    "swimming": {"swimming_lane_present", "lane_rope_present", "swim_cap_present", "swim_goggles_present"},
    "yoga": {"yoga_mat_present", "yoga_studio_present"},
    "pilates": {"pilates_reformer_present", "pilates_equipment_present", "pilates_studio_present"},
    "home_workout": {
        "exercise_mat_present",
        "resistance_band_present",
        "home_dumbbell_present",
        "kettlebell_present",
        "pull_up_bar_present",
    },
}

_EXERCISE_POSE_EVIDENCE = {
    "exercise_pose_visible",
    "yoga_pose_visible",
    "pilates_pose_visible",
    "home_exercise_pose_visible",
}


def _exercise_mandatory_passed(analysis: VisionAnalysis, context: ImageVerificationContext) -> bool:
    activity = context.exercise_activity_type
    if activity is None:
        return False
    exercise_evidence = _exercise_evidence(analysis)
    if "home_workout" == activity and exercise_evidence == {"home_workout_environment"}:
        return False
    if activity == "yoga":
        return (
            "yoga_studio_present" in exercise_evidence
            or "yoga_pose_visible" in exercise_evidence
            or {"yoga_environment", "yoga_mat_present"}.issubset(exercise_evidence)
        )
    if activity == "home_workout":
        # 홈트는 기구가 없을 수 있다. 다음이면 통과:
        #  - 홈 기구(매트/밴드/덤벨/케틀벨/풀업바) 존재, 또는
        #  - 홈 운동 자세(home_exercise_pose_visible), 또는
        #  - 홈 운동 환경 + 자세(일반/홈) 조합.
        # 환경 단독(home_workout_environment only)은 위 상단 가드에서 이미 False → 자세 단독 PASS 금지 유지.
        home_core = exercise_evidence & _EXERCISE_CORE_EQUIPMENT.get("home_workout", set())
        if home_core or "home_exercise_pose_visible" in exercise_evidence:
            return True
        if "home_workout_environment" in exercise_evidence and (
            exercise_evidence & _EXERCISE_POSE_EVIDENCE
        ):
            return True
        return False
    # 핵심 기구/장소 단서(예: gym treadmill_present)는 해당 운동 환경을 함의한다.
    # 로컬 VLM 이 gym_environment 같은 환경 라벨을 별도로 내지 않고 treadmill_present 만 내는
    # 매핑 누락을 보완: 해당 activity 의 핵심 근거가 있으면 필수 조건을 통과로 본다.
    # (핵심 라벨은 실제 기구/장소만 포함 → food/bedroom/office/water/shoes 등 부정 케이스는
    #  이 라벨을 얻지 못하므로 FP 가 생기지 않는다. 자세(pose)는 기존대로 보너스로만 취급.)
    if exercise_evidence.intersection(_EXERCISE_CORE_EQUIPMENT.get(activity, set())):
        return True
    return all(bool(exercise_evidence.intersection(group)) for group in _EXERCISE_REQUIRED[activity])


def _append_exercise_priority_evidence(
    analysis: VisionAnalysis,
    context: ImageVerificationContext,
    evidence: list[RuleEvidence],
) -> None:
    exercise_evidence = _exercise_evidence(analysis)
    if "unrelated_environment" in exercise_evidence:
        evidence.append(RuleEvidence(code="exercise_priority:unrelated_environment", message="운동과 무관한 환경입니다."))
    if "wrong_activity_environment" in exercise_evidence or _has_wrong_activity_environment(exercise_evidence, context.exercise_activity_type):
        evidence.append(
            RuleEvidence(
                code="exercise_priority:wrong_activity_environment",
                message="요청한 운동과 다른 강한 운동 환경이 확인되었습니다.",
            )
        )
    if "uncertain_exercise_environment" in exercise_evidence:
        evidence.append(
            RuleEvidence(code="exercise_priority:uncertain_exercise_environment", message="운동 환경인지 확실하지 않습니다.")
        )
    if "insufficient_exercise_evidence" in exercise_evidence:
        evidence.append(
            RuleEvidence(code="exercise_priority:insufficient_exercise_evidence", message="운동 환경 근거가 부족합니다.")
        )


def _has_wrong_activity_environment(evidence: set[str], activity: ExerciseActivityType | None) -> bool:
    if activity is None:
        return False
    selected = _EXERCISE_ACTIVITY_EVIDENCE[activity]
    for other_activity, strong_evidence in _EXERCISE_STRONG_ENVIRONMENT.items():
        if other_activity != activity and evidence.intersection(strong_evidence) and not evidence.intersection(selected):
            return True
    return False


def _score_exercise(
    rule: dict[str, Any],
    analysis: VisionAnalysis,
    context: ImageVerificationContext,
    breakdown: RuleScoreBreakdown,
    evidence: list[RuleEvidence],
) -> None:
    activity = context.exercise_activity_type
    if activity is None:
        return
    exercise_evidence = _exercise_evidence(analysis)
    strong_env = exercise_evidence.intersection(_EXERCISE_STRONG_ENVIRONMENT[activity])
    if strong_env:
        breakdown.object_score += 30
        evidence.append(
            RuleEvidence(
                code=f"exercise_environment:{activity}",
                message="선택한 운동과 관련된 환경이 확인되었습니다.",
                score_delta=30,
            )
        )

    core_count = len(exercise_evidence.intersection(_EXERCISE_CORE_EQUIPMENT[activity]))
    if core_count:
        delta = min(core_count * 20, 35)
        breakdown.object_score += delta
        evidence.append(
            RuleEvidence(
                code=f"exercise_core_equipment:{activity}",
                message="선택한 운동과 관련된 핵심 기구 또는 장소 단서가 확인되었습니다.",
                score_delta=delta,
            )
        )

    support = exercise_evidence.intersection({"exercise_environment", "exercise_equipment_present"})
    if support:
        breakdown.object_score += 10
        evidence.append(RuleEvidence(code="exercise_supporting_evidence", message="운동 관련 보조 근거가 확인되었습니다.", score_delta=10))

    pose = exercise_evidence.intersection(_EXERCISE_POSE_EVIDENCE)
    if pose:
        breakdown.object_score += 10
        evidence.append(RuleEvidence(code="exercise_pose_bonus", message="운동 자세는 보너스 근거로만 반영되었습니다.", score_delta=10))

    if activity in {"running", "swimming"}:
        evidence.append(
            RuleEvidence(
                code=f"exercise_limitation:{activity}",
                message="현재 판정은 운동 완료가 아니라 선택한 운동 환경 인증입니다.",
            )
        )

    if _exercise_mandatory_passed(analysis, context):
        current_exercise_score = sum(
            item.score_delta
            for item in evidence
            if item.code.startswith("exercise_") and item.score_delta > 0
        )
        mandatory_match = rule.get("scoring", {}).get("mandatory_match", {}) or {}
        minimum_score = int(
            mandatory_match.get("minimum_score")
            or rule.get("thresholds", {}).get("verified", 0)
            or 0
        )
        if minimum_score > 0 and current_exercise_score < minimum_score:
            delta = minimum_score - current_exercise_score
            breakdown.object_score += delta
            evidence.append(
                RuleEvidence(
                    code=f"exercise_mandatory_match:{activity}",
                    message="선택한 운동의 필수 환경 조건을 충족해 최소 인증 점수를 적용했습니다.",
                    score_delta=delta,
                )
            )


def _priority_result(evidence: list[RuleEvidence]) -> VerificationResult | None:
    codes = {item.code for item in evidence}
    if codes.intersection({"water_priority:empty_container", "water_priority:non_water_beverage"}):
        return "rejected"
    if codes.intersection({"water_priority:opaque_closed_container", "water_priority:uncertain_liquid"}):
        return "retake_required"
    if codes.intersection({"exercise_priority:unrelated_environment", "exercise_priority:wrong_activity_environment"}):
        return "rejected"
    if "exercise_priority:uncertain_exercise_environment" in codes:
        return "retake_required"
    if "exercise_priority:insufficient_exercise_evidence" in codes:
        return "rejected"
    if codes.intersection(
        {
            "study_priority:gaming_content",
            "study_priority:entertainment_video",
            "study_priority:social_media",
            "study_priority:shopping_content",
            "study_priority:non_study_screen",
        }
    ):
        return "rejected"
    if "study_priority:uncertain_screen_content" in codes:
        return "retake_required"
    return None


def _within_minutes(captured_at: str, scheduled_at: str, window_minutes: int) -> bool:
    try:
        captured = datetime.fromisoformat(captured_at)
        scheduled = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return False
    delta = abs((captured - scheduled).total_seconds()) / 60
    return delta <= window_minutes


def _gps_score(rule: dict[str, Any], context: ImageVerificationContext) -> int:
    gps_rule = rule.get("gps", {}) or {}
    if context.location is None or context.target_location is None:
        return 0
    distance = _distance_meters(
        context.location.latitude,
        context.location.longitude,
        context.target_location.latitude,
        context.target_location.longitude,
    )
    radius = float(gps_rule.get("radius_meters", 100) or 100)
    if distance <= radius:
        return min(5, int(gps_rule.get("max_score", 5) or 5))
    return 0


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * earth_radius * asin(sqrt(a))
