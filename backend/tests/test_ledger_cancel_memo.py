"""회귀 테스트: CANCEL(결제취소) 순집계 + memo 저장/삭제.

- CANCEL 거래는 같은 기간/카테고리의 지출을 '차감'하고 income 으로 새지 않는다.
- 월 지출 합계는 음수로 내려가지 않는다(0 클램프).
- memo 는 PATCH 로 저장되고, 조회 응답에 실려오며, 빈 문자열로 삭제된다.

임시 SQLite + TestClient. 날짜는 date.today() 기준(고정 연/월 금지).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db

U = {"user_id": "local-user"}


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "ledger_cancel_memo.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _ym() -> str:
    return date.today().strftime("%Y-%m")


def _iso(hour: int, minute: int = 0) -> str:
    return f"{date.today().isoformat()}T{hour:02d}:{minute:02d}:00"


def _simulate(client, body: str, received_at: str) -> dict:
    return client.post(
        "/api/v1/ledger/notifications/simulate",
        json={**U, "body": body, "received_at": received_at},
    ).json()["data"]


def _dashboard(client) -> dict:
    return client.get(
        "/api/v1/ledger/dashboard", params={**U, "month": _ym()}
    ).json()["data"]


# --- CANCEL 순집계 ----------------------------------------------------------
def test_cancel_reduces_month_expense(client):
    _simulate(client, "스타벅스 10,000원 승인", _iso(9))
    _simulate(client, "스타벅스 3,000원 결제취소", _iso(10))
    summary = _dashboard(client)["summary"]
    assert summary["month_expense"] == 7000, summary
    assert summary["month_income"] == 0, summary


def test_over_cancel_clamps_to_zero(client):
    _simulate(client, "쿠팡 5,000원 승인", _iso(9))
    _simulate(client, "쿠팡 8,000원 결제취소", _iso(10))
    summary = _dashboard(client)["summary"]
    assert summary["month_expense"] == 0, summary


def test_cancel_not_counted_as_income(client):
    _simulate(client, "배달의민족 12,000원 승인", _iso(9))
    _simulate(client, "배달의민족 12,000원 결제취소", _iso(10))
    summary = _dashboard(client)["summary"]
    assert summary["month_income"] == 0, summary
    assert summary["month_expense"] == 0, summary


# --- memo 저장/삭제 ---------------------------------------------------------
def _first_expense_id(client) -> str:
    tx = _simulate(client, "이디야 4,500원 승인", _iso(11))
    assert tx["transaction_id"]
    return tx["transaction_id"]


def test_memo_saved_and_returned(client):
    tid = _first_expense_id(client)
    r = client.patch(
        f"/api/v1/ledger/transactions/{tid}", json={"memo": "친구랑 저녁"}
    ).json()["data"]
    assert r["memo"] == "친구랑 저녁"

    # 조회 응답(월 전체)에도 실려온다.
    data = client.get(
        "/api/v1/ledger/transactions", params={**U, "month": _ym()}
    ).json()["data"]
    found = [t for t in data["transactions"] if t["transaction_id"] == tid]
    assert found and found[0]["memo"] == "친구랑 저녁"


def test_memo_cleared_with_empty_string(client):
    tid = _first_expense_id(client)
    client.patch(f"/api/v1/ledger/transactions/{tid}", json={"memo": "임시"})
    r = client.patch(
        f"/api/v1/ledger/transactions/{tid}", json={"memo": ""}
    ).json()["data"]
    assert r["memo"] in ("", None)


def test_memo_untouched_when_not_sent(client):
    tid = _first_expense_id(client)
    client.patch(f"/api/v1/ledger/transactions/{tid}", json={"memo": "유지"})
    # memo 미포함 PATCH(카테고리만 수정) → memo 그대로 유지.
    r = client.patch(
        f"/api/v1/ledger/transactions/{tid}", json={"category": "카페"}
    ).json()["data"]
    assert r["memo"] == "유지"
