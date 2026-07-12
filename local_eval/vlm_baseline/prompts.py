"""Qwen-3B EVIDENCE-EXTRACTION prompts (water/study/exercise).

역할 변경(중요): Qwen-3B 는 **기존 객체/장면/evidence 판독 엔진을 대체하는 evidence extractor** 다.
Qwen 은 final_result(verified/rejected)를 확정하지 않는다. 최종 판정은 기존 Rule Engine 이 한다.
따라서 프롬프트는 **evidence 추출 중심**이며 출력 스키마에 final result 가 없다.
요약 문서: QWEN3B_TASK_PROMPTS.md
"""
from __future__ import annotations

TASKS = ("water", "study", "exercise")

# Qwen 이 출력할 evidence 스키마(‑ final_result 없음).
_SCHEMA = (
    '{"task":"water|study|exercise","image_quality":"good|poor|unusable|unknown",'
    '"visible_objects":[],"visible_actions":[],"scene_type":"",'
    '"positive_evidence":[],"negative_evidence":[],"blockers":[],'
    '"uncertainty":"low|medium|high","reason":""}'
)

_COMMON = (
    "You are an image EVIDENCE EXTRACTOR that replaces the object/scene reading engine. "
    "Do NOT decide pass/fail/verified/rejected — a separate rule engine makes the final decision. "
    "CRITICAL: populate each array ONLY with items ACTUALLY visible in THIS image. If a category has "
    "nothing, use an empty array []. NEVER copy or enumerate the allowed-token list; include a token only "
    "when that thing is truly present. "
    "Put any DISQUALIFYING finding ONLY in 'blockers' (it must be actually visible); leave 'negative_evidence' "
    "empty unless noting a concretely visible non-target item. "
    "If unsure, set uncertainty=high and use the *_unclear token. Do not guess. "
    "Record visible Korean/English text in reason or visible_objects. "
    "Return ONLY one JSON object matching this schema (no extra text): " + _SCHEMA + " "
)

# task별 허용 evidence/blocker 토큰(기존 Rule Engine evidence 로 매핑되는 adapter 어휘).
_TASK = {
    "water": (
        "task=water. Decide what is ACTUALLY inside the container. "
        "positive_evidence tokens (use ONLY when clearly true): visible_water (a COLORLESS liquid with a visible "
        "liquid surface/waterline inside the container), clear_liquid_visible, transparent_container, cup_visible, "
        "bottle_visible, waterline_visible. "
        "blockers tokens (use when true): empty_cup (container looks empty / no liquid surface or waterline visible), "
        "empty_bottle, colored_beverage (liquid is yellow/green/brown/orange/red or any non-colorless tint → tea, "
        "juice, soda, etc.), coffee, juice, milk, tea, soda, opaque_container (cannot see inside), liquid_unclear. "
        "STRICT RULES for FP=0: (1) An empty-looking glass with NO visible liquid surface/waterline is empty_cup, "
        "NOT visible_water. (2) A COLORED (non-colorless) liquid is a beverage → colored_beverage, NOT water. "
        "(3) Report visible_water/clear_liquid_visible ONLY when you can clearly see a colorless liquid surface; "
        "when in doubt set uncertainty=high and use liquid_unclear. Never infer water from the container name alone."
    ),
    "study": (
        "task=study. positive_evidence tokens: open_book, textbook, notes, study_document, code_screen, "
        "lecture_material, study_related_text, writing_or_solving. "
        "blockers tokens: game, youtube, video, movie, shopping, sns, empty_desk, laptop_only, "
        "closed_book_only, screen_unclear."
    ),
    "exercise": (
        "task=exercise. positive_evidence tokens: active_exercise_pose, person_exercising, "
        "person_using_equipment, workout_action, stretching, yoga_pose, lifting_weight. "
        "blockers tokens: equipment_only, gym_background_only, workout_clothes_only, sitting, resting, "
        "selfie, folded_mat, pose_unclear. "
        "Only report a positive when an actual exercise action/use is visible; equipment alone is a blocker."
    ),
}


def build_prompt(task: str) -> str:
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    return _COMMON + _TASK[task]
