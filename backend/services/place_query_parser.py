"""Rule-based place-query parser.

Turns a user's natural-language request + structured preferences into:
    (search_query, category)

MVP is fully rule-based (no LLM calls). The public orchestrator
`build_search_query()` is deliberately thin so an LLM fallback can be slotted
in later without touching callers:

    build_search_query()  ->  _rule_based_query()          [today]
                          ->  _llm_query()  (future)       [drop-in]

Examples:
    "홍대 근처에서 저녁 먹을 만한 곳 추천해줘"  -> ("홍대 저녁 맛집", "restaurant")
    "강남에서 놀만한 곳 추천해줘"              -> ("강남 놀거리",   "activity")
    "건대 카페 추천해줘"                       -> ("건대 카페",     "cafe")
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "place_recommendation_rules.json"

# Trailing Korean particles (조사) stripped from region tokens like "강남에서".
_PARTICLES = ("에서", "에게", "으로", "이랑", "랑", "에", "의", "은", "는",
              "이", "가", "을", "를", "도", "로", "와", "과", "만")


@lru_cache(maxsize=1)
def load_place_rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _all_aliases(rules: dict) -> dict:
    return rules.get("category_aliases", {})


def _strip_particle(token: str) -> str:
    for p in _PARTICLES:
        if token.endswith(p) and len(token) > len(p) + 1:
            return token[: -len(p)]
    return token


def detect_category(text: Optional[str], explicit: Optional[str], rules: dict) -> Optional[str]:
    """Pick a category. Explicit preference wins if it is a known category;
    otherwise scan the text for the first matching alias."""
    aliases = _all_aliases(rules)
    if explicit and explicit in aliases:
        return explicit
    text = text or ""
    for category, words in aliases.items():
        if any(w in text for w in words):
            return category
    return None


def _clean_tokens(text: str, rules: dict) -> List[str]:
    """Region/keyword tokens: drop stopwords, strip particles."""
    stopwords = rules.get("stopwords", [])
    single = {s for s in stopwords if " " not in s}
    # remove multi-word stopword phrases first
    for sw in sorted((s for s in stopwords if " " in s), key=len, reverse=True):
        text = text.replace(sw, " ")
    tokens: List[str] = []
    for raw in text.split():
        t = _strip_particle(raw.strip())
        if not t or t in single:
            continue
        tokens.append(t)
    return tokens


def _is_clean_keyword(token: str) -> bool:
    """A token worth keeping verbatim in the query (e.g. '저녁', '카페').
    Filters out fuzzy filler like '놀만한' / '놀만한 곳'."""
    return len(token) >= 2 and "곳" not in token and "만한" not in token


def _rule_based_query(
    input_text: Optional[str],
    category: Optional[str],
    location_address: Optional[str],
    keywords: List[str],
    rules: dict,
) -> str:
    """Assemble a Naver search string from cleaned tokens + category suffix."""
    aliases = _all_aliases(rules)
    suffixes = rules.get("category_query_suffix", {})
    cat_words = set(aliases.get(category, [])) if category else set()

    tokens = _clean_tokens(input_text or "", rules)
    region = [t for t in tokens if t not in cat_words]
    kept_aliases = [t for t in tokens if t in cat_words and _is_clean_keyword(t)]

    parts: List[str] = []
    # fall back to structured location text when the utterance has no region
    if not region and location_address:
        parts.extend(_clean_tokens(location_address, rules))
    parts.extend(region)
    parts.extend(kept_aliases)

    # if we still have nothing, lean on preference keywords
    if not parts and keywords:
        parts.extend([k for k in keywords if _is_clean_keyword(k)])

    suffix = suffixes.get(category, "") if category else ""
    if suffix:
        parts.append(suffix)

    # de-dupe, preserve order
    seen, ordered = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return " ".join(ordered).strip()


def build_search_query(
    input_text: Optional[str],
    preferences: Optional[dict] = None,
    location: Optional[dict] = None,
) -> Tuple[str, Optional[str]]:
    """Public orchestrator: returns (query, category).

    Rule-based today; wrap-and-replace with an LLM path later by branching here.
    """
    rules = load_place_rules()
    preferences = preferences or {}
    location = location or {}

    explicit = preferences.get("category")
    keywords = preferences.get("keywords") or []
    category = detect_category(input_text, explicit, rules)

    query = _rule_based_query(
        input_text=input_text,
        category=category,
        location_address=location.get("address"),
        keywords=keywords,
        rules=rules,
    )

    # last-resort query so we never call Naver with an empty string
    if not query:
        query = (input_text or "").strip() or (location.get("address") or "").strip()

    return query, category
