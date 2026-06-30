"""Mapping helpers between the API/Pydantic layer (lowercase values, split
date/time) and the SQL layer (UPPERCASE CHECK values, single ISO datetime).

These are pure functions with safe fallbacks so a malformed value never raises
a 500; it degrades to a sensible default instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# --- enum-like casing maps (API lower <-> SQL UPPER) ------------------------
PRIORITY_TO_DB = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
PRIORITY_FROM_DB = {v: k for k, v in PRIORITY_TO_DB.items()}

STATUS_TO_DB = {
    "draft": "DRAFT", "scheduled": "SCHEDULED", "in_progress": "IN_PROGRESS",
    "completed": "COMPLETED", "cancelled": "CANCELLED",
}
STATUS_FROM_DB = {v: k for k, v in STATUS_TO_DB.items()}

# NOTE: API source ("user"/"ai") is NOT a simple upper() of the SQL value.
# SQL source_type is MANUAL/AI/EXTERNAL_SYNC, so "user" maps to "MANUAL".
SOURCE_TO_DB = {
    "user": "MANUAL", "manual": "MANUAL", "ai": "AI",
    "external_sync": "EXTERNAL_SYNC",
}
SOURCE_FROM_DB = {"MANUAL": "user", "AI": "ai", "EXTERNAL_SYNC": "external_sync"}


def priority_to_db(value: Optional[str], default: str = "MEDIUM") -> str:
    return PRIORITY_TO_DB.get((value or "").lower(), default)


def priority_from_db(value: Optional[str]) -> str:
    return PRIORITY_FROM_DB.get(value or "", "medium")


def status_to_db(value: Optional[str], default: str = "SCHEDULED") -> str:
    return STATUS_TO_DB.get((value or "").lower(), default)


def status_from_db(value: Optional[str]) -> str:
    return STATUS_FROM_DB.get(value or "", "scheduled")


def source_to_db(value: Optional[str], default: str = "MANUAL") -> str:
    return SOURCE_TO_DB.get((value or "").lower(), default)


def source_from_db(value: Optional[str]) -> str:
    return SOURCE_FROM_DB.get(value or "", "user")


# --- date/time <-> ISO datetime --------------------------------------------
def now_iso() -> str:
    """Naive ISO timestamp 'YYYY-MM-DDTHH:MM:SS' (matches start_at format)."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def combine_date_time(date: Optional[str], time: Optional[str]) -> Optional[str]:
    """'YYYY-MM-DD' + 'HH:mm' -> 'YYYY-MM-DDTHH:mm:00'. None if either missing."""
    if not date or not time:
        return None
    return f"{date}T{time}:00"


def date_from_dt(dt: Optional[str]) -> Optional[str]:
    """Extract 'YYYY-MM-DD' from an ISO datetime/date string."""
    if not dt:
        return None
    return dt[:10]


def time_from_dt(dt: Optional[str]) -> Optional[str]:
    """Extract 'HH:mm' from an ISO datetime string ('...THH:mm:ss')."""
    if not dt or len(dt) < 16 or "T" not in dt:
        return None
    return dt[11:16]
