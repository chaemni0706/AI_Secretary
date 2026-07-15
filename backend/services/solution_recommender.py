"""Solution policy recommender.

Given the intent, empathy result and (optional) schedule context, choose ONE
top-level solution category and concrete solution_type(s). Categories are fixed
(immediate_recovery / schedule_support / task_structuring / environment_shift /
schedule_adjustment / safety) and the selection ORDER follows the spec:

    1. risk expression                                 -> safety
    2. free time < 10 min                              -> immediate_recovery
    3. an important event is imminent                  -> schedule_support
    4. many tasks / feeling overwhelmed                -> task_structuring
    5. free time >= 30 min + location/taste info       -> environment_shift
    6. user wants to postpone + low/medium priority ev -> schedule_adjustment
    7. ambiguous                                        -> immediate_recovery + task_structuring

Never raises. Every solution carries requires_user_confirmation = true.

Public API:
    load_solution_rules() -> dict
    select_solution_category(intent_result, empathy_result, schedule_context, user_message) -> dict
    build_solution_candidates(category, context) -> list
    rank_solutions(candidates, context) -> list
    recommend_solutions(intent_result, empathy_result, schedule_context, user_profile, user_message) -> dict
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "solution_rules.json"

IMPORTANT_CATEGORIES = {"hospital", "exam", "interview", "meeting", "deadline", "reservation"}
IMMINENT_MINUTES = 90  # an important event within this window counts as "imminent"


@lru_cache(maxsize=1)
def load_solution_rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(k in (text or "") for k in keywords)


def _free_minutes_until_next(schedule_context: Optional[dict]) -> Optional[int]:
    """Minutes from current_time until the next event start. None if unknown."""
    if not schedule_context:
        return None
    now = _parse_dt(schedule_context.get("current_time"))
    if now is None:
        return None
    starts = []
    for ev in schedule_context.get("today_schedule", []) or []:
        s = _parse_dt(ev.get("start_time"))
        if s is not None and s >= now:
            starts.append(s)
    if not starts:
        return None
    return int((min(starts) - now).total_seconds() // 60)


def _imminent_important_event(schedule_context: Optional[dict]) -> bool:
    if not schedule_context:
        return False
    now = _parse_dt(schedule_context.get("current_time"))
    if now is None:
        return False
    for ev in schedule_context.get("today_schedule", []) or []:
        s = _parse_dt(ev.get("start_time"))
        if s is None or s < now:
            continue
        gap = (s - now).total_seconds() / 60
        cat = (ev.get("category") or "").lower()
        prio = (ev.get("priority") or "").lower()
        important = cat in IMPORTANT_CATEGORIES or prio == "high" or ev.get("is_fixed")
        if important and 0 <= gap <= IMMINENT_MINUTES:
            return True
    return False


def _has_adjustable_event(schedule_context: Optional[dict], rules: dict) -> bool:
    if not schedule_context:
        return False
    adjustable = set(rules.get("adjustable_priorities", ["low", "medium"]))
    for ev in schedule_context.get("today_schedule", []) or []:
        cat = (ev.get("category") or "").lower()
        prio = (ev.get("priority") or "").lower()
        if ev.get("is_fixed"):
            continue
        if cat in IMPORTANT_CATEGORIES:
            continue
        if prio in adjustable:
            return True
    return False


def _has_location_or_taste(user_profile: Optional[dict]) -> bool:
    if not user_profile:
        return False
    return bool(
        (user_profile.get("preferred_activity") or [])
        or (user_profile.get("favorite_foods") or [])
    )


def select_solution_category(
    intent_result: dict,
    empathy_result: dict,
    schedule_context: Optional[dict],
    user_message: str,
    user_profile: Optional[dict] = None,
) -> dict:
    """Return {"category", "reason_tag", "combo"(optional list)}."""
    rules = load_solution_rules()
    text = user_message or ""
    intent = (intent_result or {}).get("intent", "fallback")

    # 1. risk expression -> safety
    if _has_any(text, rules.get("risk_keywords", [])):
        return {"category": "safety", "reason_tag": "risk"}

    free_min = _free_minutes_until_next(schedule_context)

    # 2. free time < 10 min -> immediate_recovery
    if free_min is not None and free_min < 10:
        return {"category": "immediate_recovery", "reason_tag": "no_free_time"}

    # 3. important event imminent -> schedule_support
    if _imminent_important_event(schedule_context):
        return {"category": "schedule_support", "reason_tag": "imminent_important"}

    # 4. many tasks / overwhelmed -> task_structuring
    if _has_any(text, rules.get("overwhelm_keywords", [])):
        return {"category": "task_structuring", "reason_tag": "overwhelmed"}

    # 6 (checked before 5 when the user explicitly wants to postpone):
    wants_reschedule = _has_any(text, rules.get("reschedule_wish_keywords", [])) or intent == "schedule_adjustment"
    if wants_reschedule and _has_adjustable_event(schedule_context, rules):
        return {"category": "schedule_adjustment", "reason_tag": "user_reschedule_wish"}

    # 5. free >= 30 min + location/taste -> environment_shift
    if free_min is not None and free_min >= 30 and _has_location_or_taste(user_profile):
        return {"category": "environment_shift", "reason_tag": "free_and_profile"}

    # 7. ambiguous -> combo
    return {
        "category": "task_structuring",
        "reason_tag": "ambiguous_combo",
        "combo": ["immediate_recovery", "task_structuring"],
    }


def build_solution_candidates(category: str, context: Optional[dict] = None) -> List[dict]:
    """Return the solution_type dicts for a category (as plain dicts)."""
    rules = load_solution_rules()
    cat_cfg = rules["categories"].get(category)
    if not cat_cfg:
        return []
    out = []
    for st in cat_cfg["solution_types"]:
        out.append(
            {
                "category": category,
                "solution_type": st["solution_type"],
                "title": st["title"],
                "reason": st["reason"],
                "action_buttons": list(st["action_buttons"]),
                "requires_user_confirmation": True,
            }
        )
    return out


def rank_solutions(candidates: List[dict], context: Optional[dict] = None) -> List[dict]:
    """Stable ordering: keep rule order (already curated best-first)."""
    return list(candidates)


def recommend_solutions(
    intent_result: dict,
    empathy_result: dict,
    schedule_context: Optional[dict] = None,
    user_profile: Optional[dict] = None,
    user_message: str = "",
) -> dict:
    """Full pipeline -> {"category", "reason_tag", "solutions": [...]}."""
    decision = select_solution_category(
        intent_result=intent_result,
        empathy_result=empathy_result,
        schedule_context=schedule_context,
        user_message=user_message,
        user_profile=user_profile,
    )
    category = decision["category"]

    if "combo" in decision:
        solutions: List[dict] = []
        for cat in decision["combo"]:
            cands = build_solution_candidates(cat, {"schedule_context": schedule_context})
            if cands:
                solutions.append(cands[0])  # one representative per combo category
    else:
        solutions = build_solution_candidates(category, {"schedule_context": schedule_context})

    solutions = rank_solutions(solutions, {"schedule_context": schedule_context})

    return {
        "category": category,
        "reason_tag": decision.get("reason_tag"),
        "solutions": solutions,
    }
