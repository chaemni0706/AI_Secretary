"""Ledger 통합(엔드포인트 간 일관성 + 다단계 라이프사이클) 테스트 보강.

기존 단위성 테스트(파싱/대시보드/중복/pending)를 넘어서, 여러 API 를 이어
호출하는 실제 사용 흐름과 대시보드↔리포트↔월조회의 집계 일관성을 잠근다.

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
    db_file = tmp_path / "ledger_integration.db"
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


# --- helpers ----------------------------------------------------------------
def _ym() -> str:
    return date.today().strftime("%Y-%m")


def _day(d: int) -> str:
    return date.today().replace(day=d).isoformat()


def _iso(hour: int, minute: int = 0, day: int | None = None) -> str:
    base = date.today().replace(day=day) if day else date.today()
    return f"{base.isoformat()}T{hour:02d}:{minute:02d}:00"


def _simulate(client, body: str, received_at: str) -> dict:
    return client.post(
        "/api/v1/ledger/notifications/simulate",
        json={**U, "body": body, "received_at": received_at},
    ).json()["data"]


def _dashboard(client) -> dict:
    return client.get("/api/v1/ledger/dashboard", params={**U, "month": _ym()}).json()["data"]


def _report(client) -> dict:
    return client.get("/api/v1/ledger/report", params={**U, "month": _ym()}).json()["data"]


def _transactions(client, **extra) -> dict:
    return client.get(
        "/api/v1/ledger/transactions", params={**U, "month": _ym(), **extra}
    ).json()["data"]


# --- 1) 대시보드 ↔ 리포트 ↔ 월조회 집계 일관성 ------------------------------
def test_summaries_consistent_across_endpoints(client):
    _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    _simulate(client, "쿠팡 33,900원 승인", _iso(12))
    _simulate(client, "급여 2,000,000원 입금", _iso(8))

    d = _dashboard(client)["summary"]
    r = _report(client)["summary"]
    t = _transactions(client)["summary"]

    for key in ("month_expense", "month_income"):
        assert d[key] == r[key] == t[key], (key, d, r, t)
    # 잔액 = 수입 - 지출 (세 곳 동일)
    assert r["balance"] == r["month_income"] - r["month_expense"]


# --- 2) 전체 라이프사이클: 등록 → 확정 → 삭제, 각 뷰 반영 --------------------
def test_full_lifecycle_confirm_and_delete(client):
    a = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    b = _simulate(client, "쿠팡 33,900원 승인", _iso(12))
    c = _simulate(client, "카카오T 12,000원 승인", _iso(18))
    ids = {"a": a["transaction_id"], "b": b["transaction_id"], "c": c["transaction_id"]}
    assert all(ids.values())

    client.post(f"/api/v1/ledger/transactions/{ids['a']}/confirm")
    client.delete(f"/api/v1/ledger/transactions/{ids['b']}")

    tx_ids = {t["transaction_id"]: t for t in _transactions(client)["transactions"]}
    # 삭제된 b 는 어디에도 없다.
    assert ids["b"] not in tx_ids
    # 확정된 a 는 목록에 남고 status=confirmed.
    assert tx_ids[ids["a"]]["status"] == "confirmed"
    # 미확정 c 는 그대로 pending.
    assert tx_ids[ids["c"]]["status"] == "pending"

    pending_ids = {p["transaction_id"] for p in _dashboard(client)["pending_transactions"]}
    assert ids["a"] not in pending_ids  # 확정 → pending 아님
    assert ids["b"] not in pending_ids  # 삭제 → pending 아님
    assert ids["c"] in pending_ids       # 미확정 → pending 유지

    # 월 지출 = a + c (b 삭제 제외).
    assert _dashboard(client)["summary"]["month_expense"] == 5800 + 12000


# --- 3) 거래 수정으로 날짜 이동 시 달력/월조회 그룹이 따라 이동 --------------
def test_update_occurred_at_moves_day(client):
    tx = _simulate(client, "이디야 4,500원 승인", _iso(9, day=10))
    tid = tx["transaction_id"]
    assert tx["date"] == _day(10)

    # 같은 달 다른 날(20일 10:00)로 이동.
    r = client.patch(
        f"/api/v1/ledger/transactions/{tid}",
        json={"occurred_at": _iso(10, day=20)},
    ).json()["data"]
    assert r["date"] == _day(20) and r["time"] == "10:00"

    by_date = {g["date"]: g for g in _transactions(client)["by_date"]}
    assert _day(20) in by_date
    assert _day(10) not in by_date  # 옛 날짜 그룹엔 더 이상 없음
    assert any(t["transaction_id"] == tid for t in by_date[_day(20)]["transactions"])


# --- 4) 카테고리 수정 → user_override + 확인필요 해제 ------------------------
def test_update_category_sets_user_override(client):
    tx = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    tid = tx["transaction_id"]
    r = client.patch(
        f"/api/v1/ledger/transactions/{tid}", json={"category": "간식"}
    ).json()["data"]
    assert r["category"] == "간식"
    assert r["category_source"] == "user_override"
    assert r["needs_user_confirmation"] is False


# --- 5) 취소가 리포트 카테고리 집계에도 순액으로 반영 ------------------------
def test_cancel_nets_in_report_category(client):
    _simulate(client, "스타벅스 10,000원 승인", _iso(9))
    _simulate(client, "스타벅스 4,000원 결제취소", _iso(10))

    rep = _report(client)
    assert rep["summary"]["month_expense"] == 6000
    cats = {c["category"]: c["amount"] for c in rep["category_analysis"]}
    # 카페 순지출 = 10000 - 4000 = 6000 (카테고리 라벨은 파서 규칙에 따름).
    assert 6000 in cats.values(), cats


# --- 6) status 필터(복수) --------------------------------------------------
def test_transactions_status_filter_multi(client):
    a = _simulate(client, "스타벅스 5,800원 승인", _iso(9))
    b = _simulate(client, "쿠팡 33,900원 승인", _iso(12))
    client.post(f"/api/v1/ledger/transactions/{a['transaction_id']}/confirm")

    only = _transactions(client, status="confirmed,pending")["transactions"]
    statuses = {t["status"] for t in only}
    assert statuses <= {"confirmed", "pending"}
    ids = {t["transaction_id"] for t in only}
    assert a["transaction_id"] in ids and b["transaction_id"] in ids


# --- 7) 광고/안내 알림은 저장 안 되고 어떤 집계에도 안 잡힘 ------------------
def test_ad_notification_not_stored_anywhere(client):
    before = _transactions(client)["summary"]["transaction_count"]
    res = _simulate(client, "[이벤트] 쿠폰 지급 안내 확인하세요", _iso(9))
    assert res.get("stored") is False
    after = _transactions(client)["summary"]["transaction_count"]
    assert after == before
