"""Shared ledger helpers: internal categories, merchant normalization, amount
parsing, and lightweight rule-file loading with in-code fallback.

Everything here is dependency-free (stdlib only). Rule JSON files live under
``backend/rules``; if a file is missing or corrupt we fall back to a small
in-code default so the server never dies (matches the existing empathy_engine /
briefing_generator convention).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"

# Canonical internal categories (order matters for stable display).
INTERNAL_CATEGORIES: List[str] = [
    "식비", "카페", "편의점", "마트_장보기", "교통", "쇼핑", "구독_콘텐츠",
    "문화_여가", "의료_약국", "교육", "미용", "생활", "통신_공과금",
    "금융_보험", "수입", "기타",
]
FALLBACK_CATEGORY = "기타"


def _load_json(filename: str, default: Any) -> Any:
    """Load a rules JSON file; return ``default`` if missing/corrupt."""
    path = _RULES_DIR / filename
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


@lru_cache(maxsize=1)
def load_notification_rules() -> Dict[str, List[str]]:
    return _load_json(
        "ledger_notification_rules.json",
        {
            "expense_keywords": ["결제", "승인", "출금", "납부", "자동이체"],
            "income_keywords": ["입금", "급여", "환급", "캐시백"],
            "cancel_keywords": ["취소", "환불"],
            "ignore_keywords": ["광고", "이벤트", "쿠폰"],
        },
    )


@lru_cache(maxsize=1)
def load_merchant_category_rules() -> Dict[str, List[str]]:
    return _load_json("merchant_category_rules.json", {})


@lru_cache(maxsize=1)
def load_merchant_search_mock() -> List[Dict[str, Any]]:
    data = _load_json("merchant_search_mock.json", [])
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def load_category_mapping_rules() -> Dict[str, str]:
    return _load_json("category_mapping_rules.json", {})


@lru_cache(maxsize=1)
def load_budget_rules() -> Dict[str, Any]:
    return _load_json(
        "ledger_budget_rules.json",
        {
            "default_monthly_budgets": {},
            "warning_threshold": 80,
            "exceeded_threshold": 100,
            "status_labels": {"normal": "정상", "warning": "주의", "exceeded": "초과"},
        },
    )


# --- Amount parsing ---------------------------------------------------------
# Matches "5,800원", "5800원", "9,800 원", "17,000 결제", "합계 9,800원".
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*원?")


def extract_amounts(text: str) -> List[int]:
    """Return all won amounts found in text, in order of appearance."""
    out: List[int] = []
    for m in _AMOUNT_RE.finditer(text or ""):
        raw = m.group(1).replace(",", "")
        try:
            out.append(int(raw))
        except ValueError:
            continue
    return out


def extract_first_amount(text: str) -> int:
    amounts = extract_amounts(text)
    return amounts[0] if amounts else 0


# --- Merchant normalization -------------------------------------------------
# Tokens stripped from notification/receipt text to isolate the core merchant.
_MERCHANT_STOP_TOKENS = (
    "카드승인", "체크카드", "신용카드", "결제완료", "결제취소", "승인취소",
    "매출취소", "입금취소", "자동이체", "이체완료",
    "결제", "승인", "사용", "출금", "입금", "취소", "환불", "납부",
    "카드", "원", "점", "지점",
)
_BRANCH_RE = re.compile(r"\s*(강남역점|강남점|역점|본점|지점|점)\s*$")


def normalize_merchant(merchant: str) -> str:
    """Produce a dedup/category-friendly normalized merchant string.

    - drop amounts and payment keywords
    - collapse whitespace
    - lowercase for ASCII tokens (Korean is unaffected by .lower())
    This is intentionally lightweight — not a full Korean NLP pipeline — but
    stable enough for the required test cases and dedup matching.
    """
    if not merchant:
        return ""
    s = merchant
    # remove amounts
    s = _AMOUNT_RE.sub(" ", s)
    # remove stop tokens
    for tok in _MERCHANT_STOP_TOKENS:
        s = s.replace(tok, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def extract_merchant_from_notification(body: str) -> str:
    """Best-effort merchant extraction from a notification body.

    Strategy: remove amounts and trailing payment keywords, keep the leading
    phrase. e.g. "스타벅스 강남역점 5,800원 결제" -> "스타벅스 강남역점".
    """
    if not body:
        return ""
    s = body
    # cut everything from the first amount onward as tail (keeps leading name)
    m = _AMOUNT_RE.search(s)
    if m:
        s = s[: m.start()]
    # strip payment keywords that may precede the amount
    for tok in ("결제", "승인", "사용", "출금", "입금", "취소", "환불", "납부",
                "카드승인", "체크카드", "신용카드"):
        s = s.replace(tok, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s
