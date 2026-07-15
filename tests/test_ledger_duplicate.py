"""Duplicate prevention tests.

Covers spec 2-1 (same notification twice) and 2-2 (same purchase arriving via
notification AND receipt scan).
"""

from __future__ import annotations

from tests.ledger_test_utils import client  # noqa: F401

NSIM = "/api/v1/ledger/notifications/simulate"
SCAN = "/api/v1/ledger/receipts/scan"


def _data(body):
    assert body["success"] is True, body
    return body["data"]


def _month_count(client, month="2026-12"):
    d = client.get("/api/v1/ledger/dashboard",
                   params={"user_id": "user-1", "month": month}).json()["data"]
    return d["summary"]["transaction_count"]


def test_same_notification_twice_is_deduped(client):
    payload = {
        "user_id": "user-1", "app_name": "KB국민카드", "title": "카드승인",
        "body": "스타벅스 강남역점 9,800원 결제", "received_at": "2026-12-31T14:20:00",
    }
    first = _data(client.post(NSIM, json=payload).json())
    assert first["duplicate"] is False
    assert _month_count(client) == 1

    second_body = client.post(NSIM, json=payload).json()
    second = _data(second_body)
    assert second["duplicate"] is True
    assert second["duplicated_transaction_id"] == first["transaction_id"]
    # not doubled
    assert _month_count(client) == 1


def test_notification_then_receipt_same_purchase(client):
    # notification first
    notif = _data(client.post(NSIM, json={
        "user_id": "user-1", "app_name": "KB국민카드", "title": "카드승인",
        "body": "스타벅스 강남역점 9,800원 결제", "received_at": "2026-12-31T14:20:00",
    }).json())
    assert notif["duplicate"] is False
    assert _month_count(client) == 1

    # receipt for the same purchase -> duplicate candidate
    receipt = _data(client.post(SCAN, json={
        "user_id": "user-1",
        "receipt_text": "스타벅스 강남역점\n2026-12-31 14:20\n합계 9,800원\n카드결제",
        "captured_at": "2026-12-31T14:25:00",
    }).json())
    assert receipt["duplicate"] is True
    assert receipt["duplicated_transaction_id"] == notif["transaction_id"]
    # still only one stored transaction
    assert _month_count(client) == 1


def test_amount_within_100_won_is_duplicate(client):
    base = {
        "user_id": "user-1", "app_name": "카드", "title": "카드승인",
        "received_at": "2026-12-31T14:20:00",
    }
    _data(client.post(NSIM, json={**base, "body": "스타벅스 강남역점 9,800원 결제"}).json())
    # 9,850 within ±100 of 9,800, same merchant/time -> duplicate
    second = _data(client.post(NSIM, json={
        **base, "received_at": "2026-12-31T14:25:00",
        "body": "스타벅스 강남역점 9,850원 결제",
    }).json())
    assert second["duplicate"] is True
    assert _month_count(client) == 1
