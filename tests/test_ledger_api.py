"""Ledger API tests: notification simulate, receipt scan, CRUD, OCR fallback.

Isolated temp DB via the shared `client` fixture. No OPENAI_API_KEY -> LLM
paths stay dormant; no OCR engine -> image upload returns a safe fallback.
"""

from __future__ import annotations

from tests.ledger_test_utils import client  # noqa: F401  (pytest fixture)

NSIM = "/api/v1/ledger/notifications/simulate"
SCAN = "/api/v1/ledger/receipts/scan"
SCAN_IMG = "/api/v1/ledger/receipts/scan-image"

RECEIPT = (
    "스타벅스 강남역점\n2026-12-31 14:20\n"
    "아이스 아메리카노 4,500\n카페라떼 5,300\n합계 9,800원\n카드결제"
)


def _env(body, success=True):
    assert {"success", "message", "data"}.issubset(body.keys()), body
    assert body["success"] is success
    return body["data"]


def test_notification_starbucks(client):
    r = client.post(NSIM, json={
        "user_id": "user-1", "app_name": "KB국민카드", "title": "카드승인",
        "body": "스타벅스 강남역점 5,800원 결제", "received_at": "2026-12-31T14:20:00",
    })
    assert r.status_code == 200, r.text
    d = _env(r.json())
    assert d["transaction_type"] == "expense"
    assert d["amount"] == 5800
    assert d["category"] == "카페"
    assert d["category_source"] == "rule_based"
    assert d["source_type"] == "notification"
    assert d["duplicate"] is False


def test_notification_income(client):
    r = client.post(NSIM, json={
        "user_id": "user-1", "app_name": "은행", "title": "입금",
        "body": "급여 500,000원 입금", "received_at": "2026-12-25T09:00:00",
    })
    d = _env(r.json())
    assert d["transaction_type"] == "income"
    assert d["category"] == "수입"


def test_notification_hyundai_needs_confirmation(client):
    r = client.post(NSIM, json={
        "user_id": "user-1", "app_name": "카드", "title": "카드승인",
        "body": "더현대서울 18,000원 결제", "received_at": "2026-12-30T16:30:00",
    })
    d = _env(r.json())
    assert d["category"] == "쇼핑"
    assert d["needs_user_confirmation"] is True


def test_notification_ad_not_stored(client):
    r = client.post(NSIM, json={
        "user_id": "user-1", "app_name": "카드", "title": "이벤트",
        "body": "혜택 쿠폰 안내", "received_at": "2026-12-31T10:00:00",
    })
    d = _env(r.json())
    assert d["transaction_type"] == "ignore"
    assert d.get("stored") is False
    # dashboard shows no transactions for that month
    dash = client.get("/api/v1/ledger/dashboard",
                      params={"user_id": "user-1", "month": "2026-12"})
    assert _env(dash.json())["summary"]["transaction_count"] == 0


def test_receipt_scan(client):
    r = client.post(SCAN, json={
        "user_id": "user-1", "receipt_text": RECEIPT,
        "captured_at": "2026-12-31T14:25:00",
    })
    d = _env(r.json())
    assert d["merchant"] == "스타벅스 강남역점"
    assert d["amount"] == 9800
    assert d["category"] == "카페"
    assert len(d["items"]) == 2
    assert d["source_type"] == "receipt_scan"


def test_confirm_update_delete(client):
    created = _env(client.post(NSIM, json={
        "user_id": "user-1", "app_name": "카드", "title": "카드승인",
        "body": "이디야 4,000원 결제", "received_at": "2026-12-20T10:00:00",
    }).json())
    tid = created["transaction_id"]

    # confirm
    c = _env(client.post(f"/api/v1/ledger/transactions/{tid}/confirm").json())
    assert c["status"] == "confirmed"

    # update category -> user_override
    u = _env(client.patch(f"/api/v1/ledger/transactions/{tid}",
                          json={"category": "식비"}).json())
    assert u["category"] == "식비"
    assert u["category_source"] == "user_override"

    # delete (soft)
    d = _env(client.delete(f"/api/v1/ledger/transactions/{tid}").json())
    assert d["deleted"] is True
    assert client.get(
        "/api/v1/ledger/dashboard",
        params={"user_id": "user-1", "month": "2026-12", "selected_date": "2026-12-20"},
    ).json()["data"]["selected_date"]["transactions"] == []


def test_missing_transaction_404(client):
    assert client.post("/api/v1/ledger/transactions/nope/confirm").status_code == 404
    assert client.patch("/api/v1/ledger/transactions/nope",
                        json={"category": "카페"}).status_code == 404
    assert client.delete("/api/v1/ledger/transactions/nope").status_code == 404


def test_image_upload_ocr_unavailable_is_safe(client):
    # No OCR engine installed -> must NOT 500; returns needs_review fallback.
    r = client.post(
        SCAN_IMG,
        data={"user_id": "user-1", "captured_at": "2026-12-31T14:25:00"},
        files={"file": ("receipt.jpg", b"\xff\xd8\xff\xe0notarealimage", "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    d = _env(r.json())
    assert d["status"] == "needs_review"
    assert d["stored"] is False
