"""Virtual (mock) business catalog.

Loads businesses from ``backend/rules/virtual_businesses.json`` — the same
rules/*.json convention used elsewhere in the project. No external API. All
lookups degrade safely: a missing/malformed file or bad row yields an empty
catalog rather than raising, so the API layer never returns a 500 from here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from backend.database.schema.reservation_business_schema import VirtualBusiness

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "virtual_businesses.json"


@lru_cache(maxsize=1)
def _load() -> List[VirtualBusiness]:
    """Parse the seed file once. Any failure -> empty catalog (logged shape kept simple)."""
    try:
        raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = raw.get("businesses", []) if isinstance(raw, dict) else raw
    businesses: List[VirtualBusiness] = []
    for row in rows or []:
        try:
            businesses.append(VirtualBusiness(**row))
        except (ValidationError, TypeError):
            continue  # skip malformed entries, keep the rest
    return businesses


def list_businesses() -> List[VirtualBusiness]:
    """All seeded businesses."""
    return list(_load())


def list_by_category(category: Optional[str]) -> List[VirtualBusiness]:
    """Businesses whose category matches (case-insensitive). None -> all."""
    if not category:
        return list_businesses()
    cat = category.strip().lower()
    return [b for b in _load() if b.category.lower() == cat]


def get_business(business_id: str) -> Optional[VirtualBusiness]:
    """Single business by id, or None if not found."""
    for b in _load():
        if b.business_id == business_id:
            return b
    return None
