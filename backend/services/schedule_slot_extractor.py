"""Schedule date/time/location slot extractor.

Extracts ONLY what the user actually said — it never fabricates a date, time or
location. Anything absent is reported via ``missing_fields`` so the orchestrator
can enter a clarification flow instead of inventing values.

Date/time reuse the battle-tested helpers from ``schedule_parser`` (so resolved
values stay identical to the legacy ``/ai/schedule/parse`` endpoint). Location
uses the JSON pattern rule-base and rejects bare category nouns (병원) so that
only a *specific* place (포항성모병원) counts as an extracted location.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from backend.services import schedule_rule_loader as rules

# Reuse the existing, tested rule helpers (no duplication, no behaviour drift).
from backend.services.schedule_parser import (
    _add_one_hour,
    _extract_date,
    _extract_time,
)

# trailing particles stripped from a captured location token
_LOC_PARTICLES = ("에서", "으로", "로", "에", "은", "는", "이", "가", "을", "를")


def _resolve_base(current_datetime: Optional[str]) -> datetime:
    if current_datetime:
        try:
            return datetime.fromisoformat(current_datetime)
        except ValueError:
            pass
    return datetime.now()


def _is_specific_place(candidate: str) -> bool:
    """A location is specific only if it isn't just a bare category/place noun
    (병원, 카페, 미용실 ...). '포항성모병원' -> True, '병원' -> False."""
    if not candidate or len(candidate) < 2:
        return False
    policy = rules.load_location_policy()
    generic = set(policy.get("place_required_keywords", [])) | set(
        rules.all_category_keywords()
    )
    return candidate not in generic


def _strip_particles(token: str) -> str:
    for p in _LOC_PARTICLES:
        if token.endswith(p) and len(token) > len(p):
            return token[: -len(p)]
    return token


def extract_location(text: str) -> Optional[str]:
    """Return a specific location grounded in the text, or None."""
    for _name, rx, _conf in rules.compiled_patterns().get("location_patterns", []):
        if "location" not in rx.groupindex:
            continue
        m = rx.search(text)
        if not m:
            continue
        cand = _strip_particles((m.group("location") or "").strip())
        if _is_specific_place(cand):
            return cand
    return None


def extract_schedule_slots(
    request_text: str, current_datetime: Optional[str] = None
) -> Dict:
    """Return resolved date/time/location slots without inventing missing values.

    Result keys: date, date_expression, time (== start_time), start_time,
    end_time, time_expression, ambiguous, location, missing_fields
    (only date/time here; the location requirement is category-dependent and is
    decided by the orchestrator, not this extractor).
    """
    text = (request_text or "").strip()
    base = _resolve_base(current_datetime)

    date_value, date_expr = _extract_date(text, base)
    start_time, time_expr, ambiguous = _extract_time(text)
    # end_time derived ONLY from an explicit start_time; never fabricated.
    end_time = _add_one_hour(start_time) if start_time else None
    location = extract_location(text)

    missing: List[str] = []
    if not date_value:
        missing.append("date")
    if not start_time:
        missing.append("time")

    return {
        "date": date_value,
        "date_expression": date_expr,
        "time": start_time,
        "start_time": start_time,
        "end_time": end_time,
        "time_expression": time_expr,
        "ambiguous": ambiguous,
        "location": location,
        "missing_fields": missing,
    }
