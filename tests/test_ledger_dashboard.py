"""Dashboard + report tests, driven by the idempotent mock seed.

시드는 date.today() 기준 상대 날짜로 거래를 만든다(고정 연/월 사용 안 함).
따라서 월/선택일은 현재 월 기준으로 계산하고, 특정 일자 건수처럼 '오늘 날짜에
따라 달라지는' 값은 단정하지 않는다.
"""

from __future__ import annotations

from datetime import date

from tests.ledger_test_utils import client  # noqa: F401

SEED = "/api/v1/ledger/mock/seed"
DASH = "/api/v1/ledger/dashboard"
REPORT = "/api/v1/ledger/report"


def _ym() -> str:
    return date.today().strftime("%Y-%m")


def _today() -> str:
    return date.today().isoformat()


def _data(body):
    assert body["success"] is True, body
    return body["data"]


def test_seed_is_idempotent(client):
    first = _data(client.post(SEED, params={"user_id": "user-1"}).json())
    assert first["count"] == 7
    second = _data(client.post(SEED, params={"user_id": "user-1"}).json())
    assert second["count"] == 7
    # 두 번 시드해도 이번 달 거래가 두 배로 늘지 않는다(멱등).
    # '어제'가 전월로 넘어가는 월초(1일)엔 6건, 그 외엔 7건.
    dash = _data(client.get(DASH, params={"user_id": "user-1", "month": _ym()}).json())
    assert dash["summary"]["transaction_count"] in (6, 7)


def test_dashboard_shape(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(DASH, params={
        "user_id": "user-1", "month": _ym(), "selected_date": _today(),
    }).json())
    assert "summary" in d and "calendar" in d
    assert d["calendar"], "calendar should not be empty after seed"
    sd = d["selected_date"]
    assert sd["date"] == _today()
    assert "briefing" in sd and sd["briefing"]["title"]
    # 오늘(base)엔 스타벅스(카페) 거래가 항상 있다.
    assert isinstance(sd["transactions"], list) and len(sd["transactions"]) >= 1
    # 급여(수입)는 이번 달 20일에 시드되어 항상 이번 달에 포함된다.
    assert d["summary"]["month_income"] == 500000


def test_report_shape_and_budget(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(REPORT, params={"user_id": "user-1", "month": _ym()}).json())
    assert d["month"] == _ym()
    assert d["category_analysis"], "category_analysis present"
    assert d["budget_usage"], "budget_usage present"
    assert d["briefing"]["title"]
    # every budget_usage row carries a status label
    for row in d["budget_usage"]:
        assert row["status"] in ("normal", "warning", "exceeded")


def test_recurring_payments_include_netflix_and_kt(client):
    client.post(SEED, params={"user_id": "user-1"})
    d = _data(client.get(REPORT, params={"user_id": "user-1", "month": _ym()}).json())
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
