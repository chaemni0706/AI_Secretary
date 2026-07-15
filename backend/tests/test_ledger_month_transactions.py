"""월 전체 거래내역 조회 API 회귀 테스트.

잠그는 대상:
- GET /api/v1/ledger/transactions 가 선택 날짜에 한정하지 않고 해당 월 전체를 반환.
- by_date 그룹이 날짜 내림차순, 그룹 내부는 occurred_at 내림차순.
- flat transactions 도 occurred_at 내림차순.
- summary 합계(월 지출/수입)가 dashboard 와 일치.
- DELETED 는 제외, status 필터가 동작.

임시 SQLite + TestClient. 날짜는 date.today() 기준으로만 만든다(고정 연/월 금지).
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
    db_file = tmp_path / "ledger_month_tx.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

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


def _transactions(client, **extra) -> dict:
    return client.get(
        "/api/v1/ledger/transactions", params={**U, "month": _ym(), **extra}
    ).json()["data"]


# --- 1) 선택 날짜에 한정하지 않고 월 전체를 반환 ------------------------------
def test_returns_full_month_across_days(client):
    # seed 는 여러 날짜(오늘/어제/3·8·10·15·20일)에 거래를 만든다.
    client.post("/api/v1/ledger/mock/seed", params=U)
    data = _transactions(client)

    assert data["month"] == _ym()
    assert data["summary"]["transaction_count"] == len(data["transactions"])
    # 여러 날짜에 걸쳐 있어야 한다(선택 날짜 하루만이 아님).
    dates = {t["date"] for t in data["transactions"]}
    assert len(dates) >= 2
    assert len(data["by_date"]) == len(dates)


# --- 2) by_date 는 날짜 내림차순, 그룹 내부는 최신순 --------------------------
def test_group_ordering_desc(client):
    _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    _simulate(client, "쿠팡 33,900원 승인", _iso(18))
    _simulate(client, "카카오T 12,000원 승인", _iso(12))

    data = _transactions(client)
    group_dates = [g["date"] for g in data["by_date"]]
    assert group_dates == sorted(group_dates, reverse=True)

    for g in data["by_date"]:
        occurred = [t.get("occurred_at") or "" for t in g["transactions"]]
        assert occurred == sorted(occurred, reverse=True)
        assert g["transaction_count"] == len(g["transactions"])

    flat = [t.get("occurred_at") or "" for t in data["transactions"]]
    assert flat == sorted(flat, reverse=True)


# --- 3) summary 합계가 dashboard 와 일치 -------------------------------------
def test_summary_matches_dashboard(client):
    client.post("/api/v1/ledger/mock/seed", params=U)
    tx = _transactions(client)
    dash = client.get(
        "/api/v1/ledger/dashboard", params={**U, "month": _ym()}
    ).json()["data"]["summary"]

    assert tx["summary"]["month_expense"] == dash["month_expense"]
    assert tx["summary"]["month_income"] == dash["month_income"]


# --- 4) DELETED 제외 + status 필터 -------------------------------------------
def test_excludes_deleted_and_status_filter(client):
    a = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    b = _simulate(client, "쿠팡 33,900원 승인", _iso(18))
    assert a["transaction_id"] and b["transaction_id"]

    client.post(f"/api/v1/ledger/transactions/{a['transaction_id']}/confirm")
    client.delete(f"/api/v1/ledger/transactions/{b['transaction_id']}")

    ids = {t["transaction_id"] for t in _transactions(client)["transactions"]}
    assert a["transaction_id"] in ids, "confirmed 는 조회에 포함"
    assert b["transaction_id"] not in ids, "deleted 는 제외"

    # status=confirmed 필터: confirmed 만.
    filtered = _transactions(client, status="confirmed")["transactions"]
    assert filtered, "confirmed 거래가 있어야 함"
    assert all(t["status"] == "confirmed" for t in filtered)
