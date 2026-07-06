"""LedgerNotificationParser unit tests (no DB, no LLM)."""

from __future__ import annotations

from backend.services import ledger_notification_parser as parser


def test_starbucks_expense():
    r = parser.parse(
        app_name="KB국민카드", title="카드승인",
        body="스타벅스 강남역점 5,800원 결제", received_at="2026-12-31T14:20:00",
    )
    assert r["transaction_type"] == "expense"
    assert r["amount"] == 5800
    assert "스타벅스" in r["merchant"]
    assert r["date"] == "2026-12-31"
    assert r["time"] == "14:20"
    assert r["source_type"] == "notification"


def test_income_salary():
    r = parser.parse(
        app_name="국민은행", title="입금", body="급여 500,000원 입금",
        received_at="2026-12-25T09:00:00",
    )
    assert r["transaction_type"] == "income"
    assert r["amount"] == 500000


def test_cancel_beats_expense():
    r = parser.parse(
        app_name="카드", title="승인취소", body="스타벅스 5,800원 결제취소",
        received_at="2026-12-31T15:00:00",
    )
    assert r["transaction_type"] == "cancel"


def test_ad_is_ignored():
    r = parser.parse(
        app_name="카드", title="이벤트 안내", body="특별 혜택 쿠폰이 도착했어요",
        received_at="2026-12-31T10:00:00",
    )
    assert r["transaction_type"] == "ignore"


def test_amount_formats():
    for body, expected in [
        ("결제 5800원", 5800),
        ("9,800 원 결제", 9800),
        ("17,000 결제", 17000),
    ]:
        r = parser.parse(app_name="c", title="승인", body=body,
                         received_at="2026-12-31T10:00:00")
        assert r["amount"] == expected, body
