"""Rule-based intent classifier for the AI-secretary chat.

Classifies a user utterance into one of the supported functional intents using
weighted keyword rules loaded from ``rules/chat_intent_rules.json``. Never
raises: an empty / unmatched utterance yields the ``fallback`` intent.

Public API:
    load_intent_rules() -> dict
    score_intents(text) -> dict        # {intent: score}
    select_intent(text) -> dict        # {intent, scores, matched_keywords}
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "chat_intent_rules.json"

INTENTS = (
    "schedule_create",
    "schedule_query",
    "daily_briefing",
    "reservation_recommend",
    "reservation_message",
    "schedule_adjustment",
    "emotion_coaching",
    "smalltalk",
    "fallback",
)


@lru_cache(maxsize=1)
def load_intent_rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _matched(text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def score_intents(text: str) -> Dict[str, float]:
    """Raw weighted score per intent (0 for intents with no match)."""
    rules = load_intent_rules()
    weights = rules["weights"]
    text = text or ""
    scores: Dict[str, float] = {}
    for intent, groups in rules["intents"].items():
        strong_hits = _matched(text, groups.get("strong", []))
        weak_hits = _matched(text, groups.get("weak", []))
        score = weights["strong"] * len(strong_hits) + weights["weak"] * len(weak_hits)
        scores[intent] = float(score)
    return scores


def select_intent(text: str) -> dict:
    """Pick the best intent. Ties broken by ``priority_order`` in the rules.

    Returns {"intent", "scores", "matched_keywords"}. Falls back to
    ``fallback`` when nothing matches.
    """
    rules = load_intent_rules()
    scores = score_intents(text)
    priority = rules["priority_order"]

    best_intent = "fallback"
    best_score = 0.0
    for intent in priority:
        s = scores.get(intent, 0.0)
        if s > best_score:
            best_intent, best_score = intent, s

    matched: Dict[str, List[str]] = {}
    text = text or ""
    groups = rules["intents"].get(best_intent)
    if groups:
        hits = _matched(text, groups.get("strong", [])) + _matched(text, groups.get("weak", []))
        if hits:
            matched[best_intent] = hits

    return {
        "intent": best_intent,
        "scores": scores,
        "matched_keywords": matched,
    }
