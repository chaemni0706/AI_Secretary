"""Dashboard + report tests, driven by the idempotent mock seed."""

from __future__ import annotations

from tests.ledger_test_utils import client  # noqa: F401

SEED = "/api/v1/ledger/mock/seed"
DASH = "/api/v1/ledger/dashboard"
REPORT = "/api/v1/ledger/report"


def _data(body):
    assert body["success"] is True, body
    return body["data"]


def test_seed_is_idempotent(client):
    first = _data(client.post(SEED, params={"user_id": "user-1"}).json())
    assert first["count"] == 7
    second = _data(client.post(SEED, params={"user_id": "user-1"}).json())
    assert second["count"] == 7
    # after two seeds, the month still has exactly the seed set (no doubling)
    dash = _data(client.get(DASH, params={"user_id": "user-1", "month": "2026-12"}).json())
    assert dash["summary"]["transaction_count"] == 7


def test_dashboard_shape(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(DASH, params={
        "user_id": "user-1", "month": "2026-12", "selected_date": "2026-12-31",
    }).json())
    assert "summary" in d and "calendar" in d
    assert d["calendar"], "calendar should not be empty after seed"
    sd = d["selected_date"]
    assert sd["date"] == "2026-12-31"
    assert "briefing" in sd and sd["briefing"]["title"]
    assert "transactions" in sd
    # 2026-12-31 seed rows: 스타벅스 + 홍콩반점 + 카카오T = 3
    assert len(sd["transactions"]) == 3
    assert d["summary"]["month_income"] == 500000


def test_report_shape_and_budget(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(REPORT, params={"user_id": "user-1", "month": "2026-12"}).json())
    assert d["month"] == "2026-12"
    assert d["category_analysis"], "category_analysis present"
    assert d["budget_usage"], "budget_usage present"
    assert d["briefing"]["title"]
    # every budget_usage row carries a status label
    for row in d["budget_usage"]:
        assert row["status"] in ("normal", "warning", "exceeded")


def test_recurring_payments_include_netflix_and_kt(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(REPORT, params={"user_id": "user-1", "month": "2026-12"}).json())
    merchants = {r["merchant"] for r in d["recurring_payments"]}
    assert "NETFLIX" in merchants
    assert "KT 통신비" in merchants


def test_budget_warning_status(client):
    # push 카페 over 80% of its 50,000 budget. Use distinct cafe merchants +
    # amounts so dedup does not collapse them into one transaction.
    cafes = [("스타벅스", 5800), ("투썸플레이스", 6200), ("이디야", 4500),
             ("메가커피", 3900), ("컴포즈커피", 4100), ("빽다방", 4300),
             ("할리스", 5100), ("커피빈", 6000)]
    for i, (name, amt) in enumerate(cafes):
        client.post("/api/v1/ledger/notifications/simulate", json={
            "user_id": "user-1", "app_name": "카드", "title": "카드승인",
            "body": f"{name} {amt:,}원 결제",
            "received_at": f"2026-12-{10+i:02d}T10:00:00",
        })
    d = _data(client.get(REPORT, params={"user_id": "user-1", "month": "2026-12"}).json())
    cafe = next(r for r in d["budget_usage"] if r["category"] == "카페")
    assert cafe["usage_rate"] >= 80
    assert cafe["status"] in ("warning", "exceeded")
