"""MerchantCategoryEngine — 5-stage category classification.

Pipeline (stops at first confident hit):
  1. merchant_category_rules.json  -> rule_based
  2. merchant_search_mock.json     -> mock_place_search (may set alternatives)
  3. category_mapping_rules.json   -> category_mapping (external -> internal)
  4. optional llm_service.generate -> llm  (skipped when key absent / fails)
  5. fallback                      -> 기타 / fallback / conf 0.3 / needs review

OPENAI_API_KEY absence must not break anything: stage 4 is best-effort and any
failure/None falls through to stage 5.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services import ledger_common as common
from backend.services import llm_service


def _ambiguous_mock_keywords() -> set:
    """Merchant keywords whose mock_place_search entry requires user
    confirmation. These should defer to the mock-search stage (which carries
    alternatives + needs_user_confirmation) rather than being resolved by a
    high-confidence rule_based hit."""
    out = set()
    for e in common.load_merchant_search_mock():
        if e.get("needs_user_confirmation"):
            kw = str(e.get("merchant_keyword", "")).lower()
            if kw:
                out.add(kw)
    return out


def _match_rule_based(normalized: str, raw: str) -> Optional[Dict[str, Any]]:
    rules = common.load_merchant_category_rules()
    hay = f"{raw} {normalized}".lower()
    ambiguous = _ambiguous_mock_keywords()
    # If the merchant is a known-ambiguous one, defer to mock_place_search.
    if any(kw in hay for kw in ambiguous):
        return None
    for category, keywords in rules.items():
        for kw in keywords:
            if kw.lower() in hay:
                return {
                    "category": category,
                    "category_source": "rule_based",
                    "confidence": 0.98,
                    "needs_user_confirmation": False,
                    "alternatives": [],
                }
    return None


def _match_mock_search(normalized: str, raw: str) -> Optional[Dict[str, Any]]:
    entries = common.load_merchant_search_mock()
    hay = f"{raw} {normalized}".lower()
    for e in entries:
        kw = str(e.get("merchant_keyword", "")).lower()
        if kw and kw in hay:
            needs = bool(e.get("needs_user_confirmation", False))
            return {
                "category": e.get("mapped_category", common.FALLBACK_CATEGORY),
                "category_source": "mock_place_search",
                "confidence": float(e.get("confidence", 0.9)),
                "needs_user_confirmation": needs,
                "alternatives": list(e.get("alternatives", [])) if needs else [],
            }
    return None


def _match_category_mapping(external_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    if not external_hint:
        return None
    mapping = common.load_category_mapping_rules()
    for token, internal in mapping.items():
        if token in external_hint:
            return {
                "category": internal,
                "category_source": "category_mapping",
                "confidence": 0.75,
                "needs_user_confirmation": False,
                "alternatives": [],
            }
    return None


def _match_llm(merchant: str) -> Optional[Dict[str, Any]]:
    """Optional LLM classification. Returns None if disabled/failed/invalid."""
    if not llm_service.is_enabled():
        return None
    cats = ", ".join(common.INTERNAL_CATEGORIES)
    prompt = (
        f"다음 상호명을 아래 카테고리 중 하나로만 분류해줘. 카테고리 이름만 출력.\n"
        f"상호명: {merchant}\n카테고리 목록: {cats}"
    )
    result = llm_service.generate(prompt=prompt)
    if not result:
        return None
    result = result.strip()
    if result not in common.INTERNAL_CATEGORIES:
        return None
    return {
        "category": result,
        "category_source": "llm",
        "confidence": 0.6,
        "needs_user_confirmation": True,
        "alternatives": [],
    }


def _fallback() -> Dict[str, Any]:
    return {
        "category": common.FALLBACK_CATEGORY,
        "category_source": "fallback",
        "confidence": 0.3,
        "needs_user_confirmation": True,
        "alternatives": [],
    }


def classify(
    *,
    merchant: str,
    normalized_merchant: Optional[str] = None,
    external_hint: Optional[str] = None,
    transaction_type: str = "expense",
) -> Dict[str, Any]:
    """Classify a merchant into an internal category via the 5-stage pipeline.

    ``transaction_type='income'`` short-circuits to the 수입 category.
    """
    if transaction_type == "income":
        return {
            "category": "수입",
            "category_source": "notification_rule",
            "confidence": 0.95,
            "needs_user_confirmation": False,
            "alternatives": [],
        }

    normalized = normalized_merchant or common.normalize_merchant(merchant)
    raw = merchant or ""

    for stage in (
        lambda: _match_rule_based(normalized, raw),
        lambda: _match_mock_search(normalized, raw),
        lambda: _match_category_mapping(external_hint),
        lambda: _match_llm(raw),
    ):
        hit = stage()
        if hit is not None:
            return hit
    return _fallback()
