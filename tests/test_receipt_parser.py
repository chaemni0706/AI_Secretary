"""ReceiptParser unit tests (no DB, no OCR)."""

from __future__ import annotations

from backend.services import receipt_parser

RECEIPT = (
    "스타벅스 강남역점\n"
    "2026-12-31 14:20\n"
    "아이스 아메리카노 4,500\n"
    "카페라떼 5,300\n"
    "합계 9,800원\n"
    "카드결제"
)


def test_parse_starbucks_receipt():
    r = receipt_parser.parse(receipt_text=RECEIPT, captured_at="2026-12-31T14:25:00")
    assert r["merchant"] == "스타벅스 강남역점"
    assert r["amount"] == 9800  # from 합계 line, not the item sum coincidence
    assert r["transaction_type"] == "expense"
    assert r["date"] == "2026-12-31"
    assert r["time"] == "14:20"
    assert r["source_type"] == "receipt_scan"


def test_parse_items():
    r = receipt_parser.parse(receipt_text=RECEIPT)
    names = [i["name"] for i in r["items"]]
    amounts = [i["amount"] for i in r["items"]]
    assert "아이스 아메리카노" in names
    assert "카페라떼" in names
    assert 4500 in amounts and 5300 in amounts
    # the 합계 line must NOT be captured as an item
    assert 9800 not in amounts


def test_captured_at_fallback_when_no_date():
    text = "김밥천국\n김밥 3,500\n합계 3,500원"
    r = receipt_parser.parse(receipt_text=text, captured_at="2026-11-02T12:00:00")
    assert r["date"] == "2026-11-02"
    assert r["amount"] == 3500
