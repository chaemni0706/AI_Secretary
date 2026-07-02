"""MerchantCategoryEngine unit tests. No OPENAI_API_KEY -> LLM stage is skipped,
so all assertions rely on rule_based / mock_place_search / fallback stages."""

from __future__ import annotations

from backend.services import merchant_category_engine as engine


def test_rule_based_cafe():
    r = engine.classify(merchant="스타벅스 강남역점")
    assert r["category"] == "카페"
    assert r["category_source"] == "rule_based"
    assert r["needs_user_confirmation"] is False


def test_rule_based_food():
    r = engine.classify(merchant="홍콩반점0410 강남역점")
    assert r["category"] == "식비"
    assert r["category_source"] in ("rule_based", "mock_place_search")


def test_income_shortcircuit():
    r = engine.classify(merchant="급여", transaction_type="income")
    assert r["category"] == "수입"


def test_mock_search_needs_confirmation():
    # 더현대서울 is only in the mock place search set (confidence 0.68, needs review)
    r = engine.classify(merchant="더현대서울")
    assert r["category"] == "쇼핑"
    assert r["needs_user_confirmation"] is True
    assert "기타" in r["alternatives"]


def test_unknown_merchant_falls_back():
    r = engine.classify(merchant="듣도보도못한가게XYZ")
    assert r["category"] == "기타"
    assert r["category_source"] == "fallback"
    assert r["confidence"] == 0.3
    assert r["needs_user_confirmation"] is True
