"""1차 수정 회귀 테스트 (최소 범위).

잠그는 대상:
- M1: dashboard pending_transactions 에 NEEDS_REVIEW 가 포함(PENDING 도 유지),
       CONFIRMED/DELETED 는 제외, 최신순 정렬.

임시 SQLite + TestClient 로 실제 /api/v1/ledger/* 를 호출한다. 날짜는 date.today()
기준으로만 만들며 고정 연/월(2025-12, 2026-12)을 쓰지 않는다. LLM/OCR 불필요.
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
    db_file = tmp_path / "ledger_pr.db"
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


# --- helpers ----------------------------------------------------------------
def _ym() -> str:
    return date.today().strftime("%Y-%m")


def _iso(hour: int, minute: int = 0) -> str:
    """오늘 날짜의 특정 시각(ISO). 고정 연/월 사용 안 함."""
    return f"{date.today().isoformat()}T{hour:02d}:{minute:02d}:00"


def _simulate(client, body: str, received_at: str) -> dict:
    return client.post(
        "/api/v1/ledger/notifications/simulate",
        json={**U, "body": body, "received_at": received_at},
    ).json()["data"]


def _pending(client) -> list:
    data = client.get(
        "/api/v1/ledger/dashboard", params={**U, "month": _ym()}
    ).json()["data"]
    return data["pending_transactions"]


# --- 1) NEEDS_REVIEW 포함 ----------------------------------------------------
def test_dashboard_pending_includes_needs_review(client):
    # seed 에 needs_user_confirmation=True 인 거래(더현대서울)가 NEEDS_REVIEW 로 생성된다.
    client.post("/api/v1/ledger/mock/seed", params=U)
    pend = _pending(client)
    needs_review = [p for p in pend if p["status"] == "needs_review"]
    assert needs_review, "needs_review 거래가 pending_transactions 에 포함되어야 함"
    # 응답 enum 은 소문자.
    assert all(p["status"] in {"pending", "needs_review"} for p in pend)


# --- 2) PENDING 도 계속 포함 --------------------------------------------------
def test_dashboard_pending_includes_pending(client):
    tx = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    assert tx["status"] == "pending"
    ids = {p["transaction_id"] for p in _pending(client)}
    assert tx["transaction_id"] in ids


# --- 3) CONFIRMED / DELETED 는 제외 ------------------------------------------
def test_dashboard_pending_excludes_confirmed_and_deleted(client):
    a = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    b = _simulate(client, "쿠팡 33,900원 승인", _iso(12))
    assert a["transaction_id"] and b["transaction_id"]

    client.post(f"/api/v1/ledger/transactions/{a['transaction_id']}/confirm")
    client.delete(f"/api/v1/ledger/transactions/{b['transaction_id']}")

    ids = {p["transaction_id"] for p in _pending(client)}
    assert a["transaction_id"] not in ids, "confirmed 는 pending 에서 제외되어야 함"
    assert b["transaction_id"] not in ids, "deleted 는 pending 에서 제외되어야 함"


# --- 4) 최신순 정렬 ----------------------------------------------------------
def test_pending_order_latest_first(client):
    # 서로 다른 상호/금액/시각(중복 판정 회피).
    _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    _simulate(client, "쿠팡 33,900원 승인", _iso(18))
    _simulate(client, "카카오T 12,000원 승인", _iso(12))

    pend = _pending(client)
    assert len(pend) >= 3
    occurred = [p.get("occurred_at") or "" for p in pend]
    assert occurred == sorted(occurred, reverse=True), "occurred_at 내림차순이어야 함"
