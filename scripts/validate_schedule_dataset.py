"""Validate dataset/evaluation/schedule_rule_cases.jsonl.

Usage:
    python scripts/validate_schedule_dataset.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "evaluation" / "schedule_rule_cases.jsonl"

ALLOWED_CASE_TYPES = {"regression", "known_limitation"}
ALLOWED_INTENTS = {"create_schedule", "unknown"}
ALLOWED_CATEGORIES = {
    "hospital", "meeting", "school", "study", "beauty",
    "restaurant", "exercise", "personal", "etc",
}
ALLOWED_PRIORITIES = {"low", "medium", "high"}
ALLOWED_SOURCES = {"ai", "user"}
ALLOWED_INPUT_TYPES = {"text", "voice"}
ALLOWED_MISSING_FIELDS = {"date", "time", "title", "time_ambiguity"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def fail(message: str) -> None:
    raise ValueError(message)


def check_optional_pattern(value, pattern, field, sample_id):
    if value is not None and not pattern.fullmatch(value):
        fail(f"{sample_id}: invalid {field}: {value!r}")


def validate_case(case: dict, line_no: int, ids: set[str]) -> None:
    sample_id = case.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        fail(f"line {line_no}: sample_id is required")
    if sample_id in ids:
        fail(f"line {line_no}: duplicate sample_id {sample_id}")
    ids.add(sample_id)

    case_type = case.get("case_type")
    if case_type not in ALLOWED_CASE_TYPES:
        fail(f"{sample_id}: invalid case_type {case_type!r}")

    request = case.get("request")
    if not isinstance(request, dict):
        fail(f"{sample_id}: request must be an object")
    if not isinstance(request.get("input"), str):
        fail(f"{sample_id}: request.input must be a string")
    if request.get("input_type") not in ALLOWED_INPUT_TYPES:
        fail(f"{sample_id}: invalid input_type")
    if request.get("timezone") != "Asia/Seoul":
        fail(f"{sample_id}: timezone must be Asia/Seoul")
    if not isinstance(request.get("current_datetime"), str):
        fail(f"{sample_id}: current_datetime is required for reproducible tests")

    data = case.get("expected_data")
    if not isinstance(data, dict):
        fail(f"{sample_id}: expected_data must be an object")
    if data.get("intent") not in ALLOWED_INTENTS:
        fail(f"{sample_id}: invalid intent {data.get('intent')!r}")
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        fail(f"{sample_id}: confidence must be between 0 and 1")

    slots = data.get("slots")
    draft = data.get("schedule_draft")
    if not isinstance(slots, dict) or not isinstance(draft, dict):
        fail(f"{sample_id}: slots and schedule_draft are required")

    if slots.get("category") not in ALLOWED_CATEGORIES:
        fail(f"{sample_id}: invalid category {slots.get('category')!r}")
    if draft.get("priority") not in ALLOWED_PRIORITIES:
        fail(f"{sample_id}: invalid priority {draft.get('priority')!r}")
    if draft.get("source") not in ALLOWED_SOURCES:
        fail(f"{sample_id}: invalid source {draft.get('source')!r}")

    check_optional_pattern(slots.get("date"), DATE_RE, "slots.date", sample_id)
    check_optional_pattern(slots.get("start_time"), TIME_RE, "slots.start_time", sample_id)
    check_optional_pattern(slots.get("end_time"), TIME_RE, "slots.end_time", sample_id)

    missing = data.get("missing_fields")
    if not isinstance(missing, list):
        fail(f"{sample_id}: missing_fields must be a list")
    invalid_missing = set(missing) - ALLOWED_MISSING_FIELDS
    if invalid_missing:
        fail(f"{sample_id}: invalid missing_fields {sorted(invalid_missing)}")

    for field in ("title", "category", "date", "start_time", "end_time", "location"):
        if slots.get(field) != draft.get(field):
            fail(f"{sample_id}: slots.{field} and schedule_draft.{field} differ")

    if case_type == "known_limitation":
        if not isinstance(case.get("current_behavior"), str):
            fail(f"{sample_id}: known_limitation requires current_behavior")
        if not isinstance(case.get("desired_behavior"), dict):
            fail(f"{sample_id}: known_limitation requires desired_behavior")


def main() -> int:
    if not DATASET.exists():
        print(f"Dataset not found: {DATASET}", file=sys.stderr)
        return 1

    ids: set[str] = set()
    count = 0
    with DATASET.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"line {line_no}: invalid JSON: {exc}", file=sys.stderr)
                return 1
            try:
                validate_case(case, line_no, ids)
            except ValueError as exc:
                print(exc, file=sys.stderr)
                return 1
            count += 1

    regression = 0
    limitations = 0
    with DATASET.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            if case["case_type"] == "regression":
                regression += 1
            else:
                limitations += 1

    print(f"VALID: {count} cases")
    print(f"- regression: {regression}")
    print(f"- known_limitation: {limitations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
