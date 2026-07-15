"""Load image verification YAML rules."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.database.schema.image_verification_schema import VerificationType

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules" / "image_verification"


@lru_cache(maxsize=16)
def load_rule(verification_type: VerificationType) -> dict[str, Any]:
    path = _RULES_DIR / f"{verification_type}.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid rule file: {path}")
    return data


def allowed_labels(verification_type: VerificationType) -> list[str]:
    rule = load_rule(verification_type)
    labels = rule.get("allowed_labels", [])
    return [label for label in labels if isinstance(label, str)]
