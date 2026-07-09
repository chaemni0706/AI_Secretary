"""Qwen-3B unified verification baseline — task-specific prompts.
VLM 은 evidence 를 근거로 result 를 내되, FP=0 우선(애매→retake, 부정근거→rejected).
요약 문서: QWEN3B_TASK_PROMPTS.md
"""
from __future__ import annotations

TASKS = ("water", "study", "exercise")

_SCHEMA = (
    '{"task":"water|study|exercise","result":"verified|rejected|retake_required",'
    '"positive_evidence":[],"negative_evidence":[],"uncertainty":"low|medium|high","reason":""}'
)

_COMMON = (
    "You verify whether an image shows the given activity. Judge ONLY from what is visible. "
    "Do not guess. If unsure, set uncertainty=high and result=retake_required. "
    "If a negative/blocker is present, result=rejected. Only set verified when positive evidence is "
    "clear AND no blocker AND uncertainty is not high. Do not infer contents from a container name alone. "
    "Return ONLY one JSON object matching this schema: " + _SCHEMA + " "
)

_TASK = {
    "water": (
        "task=water. positive: clear/plain water, water in a transparent cup/bottle, visible waterline/surface, "
        "drinking/pouring water. blocker(reject): empty cup/bottle, opaque tumbler, colored beverage, "
        "coffee/tea/juice/soda/milk, contents not visible/reflection only. If liquid type unclear or container "
        "nearly empty → retake_required."
    ),
    "study": (
        "task=study. positive: book/textbook/workbook, notes/handwriting, document/PDF/report, code/IDE/terminal, "
        "lecture material on screen (record Korean text if any). blocker(reject): game, youtube/video/drama, "
        "shopping, SNS, home screen/app icons, laptop only with no study content, empty desk. If screen content "
        "unclear or closed book → retake_required."
    ),
    "exercise": (
        "task=exercise. positive: active exercise action/pose (push-up/squat/running/stretching/yoga), person "
        "USING equipment, gym machine being used. blocker(reject): equipment only (no action), gym background only, "
        "workout clothes only, sitting/resting, selfie, folded/stored mat. If action is unclear or only equipment "
        "is visible → retake_required."
    ),
}


def build_prompt(task: str) -> str:
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    return _COMMON + _TASK[task]
