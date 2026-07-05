"""Loader for the schedule parsing rule-base (backend/rules/schedule_*.json).

Centralizes reading + caching of the JSON rule files so the extractor modules
(`schedule_title_extractor`, `schedule_slot_extractor`, `schedule_clarification`)
stay logic-only and data-free. All loaders are cached; call `reload_rules()` in
tests if a file is edited at runtime.

Every accessor degrades gracefully (returns empty structures) if a file is
missing or malformed, so a bad rule file can never crash the parser.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Tuple

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


def _load_json(filename: str) -> dict:
    try:
        with open(_RULES_DIR / filename, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------- #
# Raw file accessors (cached)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_categories() -> Dict[str, dict]:
    """Ordered mapping {category_key: spec}. Order == matching priority."""
    return _load_json("schedule_categories.json").get("categories", {})


@lru_cache(maxsize=1)
def load_stopwords() -> Dict[str, List[str]]:
    data = _load_json("schedule_stopwords.json")
    return {k: v for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def load_patterns() -> Dict[str, list]:
    data = _load_json("schedule_patterns.json")
    return {k: v for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def load_location_policy() -> Dict:
    data = _load_json("schedule_location_policy.json")
    return {k: v for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def load_clarification_questions() -> Dict[str, dict]:
    data = _load_json("schedule_clarification_questions.json")
    return {k: v for k, v in data.items() if not k.startswith("_")}


# --------------------------------------------------------------------------- #
# Derived helpers (cached)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def category_order() -> Tuple[str, ...]:
    return tuple(load_categories().keys())


@lru_cache(maxsize=1)
def all_category_keywords() -> frozenset:
    """Every keyword across all categories — used to reject bare category nouns
    when validating an extracted location (병원 vs 포항성모병원)."""
    kws: set = set()
    for spec in load_categories().values():
        kws.update(spec.get("keywords", []))
    return frozenset(kws)


@lru_cache(maxsize=1)
def compiled_patterns() -> Dict[str, List[Tuple[str, Pattern, float]]]:
    """{group_name: [(name, compiled_regex, confidence), ...]} for all pattern
    groups whose entries carry a 'regex'. Invalid regexes are skipped."""
    out: Dict[str, List[Tuple[str, Pattern, float]]] = {}
    for group, entries in load_patterns().items():
        compiled: List[Tuple[str, Pattern, float]] = []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or "regex" not in entry:
                continue
            try:
                rx = re.compile(entry["regex"])
            except re.error:
                continue
            compiled.append(
                (entry.get("name", ""), rx, float(entry.get("confidence", 0.0)))
            )
        if compiled:
            out[group] = compiled
    return out


def detect_category(text: str) -> Tuple[str, Optional[str]]:
    """Return (category_key, matched_keyword) using file-declared priority order.

    Categories are tried in priority order; within the first category that has
    any keyword in the text, the LONGEST matching keyword wins (so '카드값'
    beats '납부', '건강검진' beats '검진', '헬스장' beats '운동').
    Falls back to ('unknown', None) when nothing matches.
    """
    for cat in category_order():
        if cat == "unknown":
            continue
        matches = [kw for kw in load_categories()[cat].get("keywords", []) if kw and kw in text]
        if matches:
            return cat, max(matches, key=len)
    return "unknown", None


def title_rule_for(category: str, keyword: Optional[str]) -> Optional[str]:
    if not keyword:
        return None
    spec = load_categories().get(category, {})
    return spec.get("title_rules", {}).get(keyword)


def category_spec(category: str) -> dict:
    return load_categories().get(category, load_categories().get("unknown", {}))


def reload_rules() -> None:
    """Clear all caches (use after editing a rule file at runtime / in tests)."""
    for fn in (
        load_categories, load_stopwords, load_patterns, load_location_policy,
        load_clarification_questions, category_order, all_category_keywords,
        compiled_patterns,
    ):
        fn.cache_clear()
