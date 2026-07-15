"""Dataset-driven regression tests for the rule-based schedule parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import parse_schedule

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "evaluation" / "schedule_rule_cases.jsonl"


def load_regression_cases() -> list[dict]:
    cases: list[dict] = []
    with DATASET.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            if case["case_type"] == "regression":
                cases.append(case)
    return cases


CASES = load_regression_cases()


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[case["sample_id"] for case in CASES],
)
def test_schedule_parser_dataset(case: dict) -> None:
    request = ScheduleParseRequest(**case["request"])
    # Compare the locked legacy payload in JSON form. ``tts_text`` is an
    # additive response field introduced after this dataset was frozen, so it
    # is validated by dedicated TTS tests rather than treated as a regression.
    actual = parse_schedule(request).model_dump(mode="json", exclude={"tts_text"})
    assert actual == case["expected_data"]
