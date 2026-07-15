"""ledger mock seed — 날짜 상대화 & 멱등성 테스트.

단위: build_seed_rows 가 현재(또는 지정) 월 기준으로 날짜를 만들고, 월말을
monthrange 로 보정하는지.
통합: 임시 SQLite 로 POST /api/v1/ledger/mock/seed 를 두 번 호출해도 거래 수가
불필요하게 늘지 않고(=idempotent), 생성 날짜가 현재 월 안에 분포하는지.
"""

import calendar
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.services import ledger_service


# --- 단위 테스트: build_seed_rows -------------------------------------------
def test_seed_rows_count_and_enums():
    rows = ledger_service.build_seed_rows(date(2026, 7, 15))
    assert len(rows) == 7
    # enum 은 API/서비스 계층에서 소문자 문자열 규약을 따른다.
    types = {r["transaction_type"] for r in rows}
    assert types <= {"expense", "income", "cancel", "ignore"}
    assert any(r["transaction_type"] == "income" for r in rows)


def test_seed_rows_within_current_month():
    base = date(2026, 7, 15)
    rows = ledger_service.build_seed_rows(base)
    for i, r in enumerate(rows):
        d = date.fromisoformat(r["occurred_at"][:10])
        if i == 1:
            # 'yesterday' 행은 base 하루 전.
            assert d == base - timedelta(days=1)
        else:
            assert (d.year, d.month) == (base.year, base.month)


def test_seed_rows_month_start_yesterday_rolls_back():
    base = date(2026, 3, 1)
    rows = ledger_service.build_seed_rows(base)
    yesterday = date.fromisoformat(rows[1]["occurred_at"][:10])
    assert yesterday == date(2026, 2, 28)


def test_day_in_month_clamps_nonexistent_day():
    # 2월 31일은 존재하지 않으므로 월말로 보정된다.
    assert ledger_service._day_in_month(date(2024, 2, 1), 31) == date(2024, 2, 29)
    assert ledger_service._day_in_month(date(2025, 2, 1), 31) == date(2025, 2, 28)


def test_seed_rows_default_is_today():
    rows = ledger_service.build_seed_rows()
    today = date.today()
    first = date.fromisoformat(rows[0]["occurred_at"][:10])
    assert first == today


# --- 통합 테스트: /ledger/mock/seed -----------------------------------------
@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "ledger.db"
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


SEED = "/api/v1/ledger/mock/seed"


def test_seed_creates_current_month_transactions(client):
    r = client.post(SEED, params={"user_id": "seed-test"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["count"] == 7

    today = date.today()
    ym = f"{today.year:04d}-{today.month:02d}"
    # 'yesterday' 를 뺀 나머지는 모두 이번 달이어야 한다.
    current = [t for t in data["transactions"] if (t["date"] or "").startswith(ym)]
    assert len(current) >= 6
    # 응답 enum 은 소문자.
    for t in data["transactions"]:
        assert t["transaction_type"] in {"expense", "income", "cancel", "ignore"}
        assert t["status"] in {
            "pending", "confirmed", "duplicate", "deleted", "needs_review",
        }


def test_seed_is_idempotent(client):
    first = client.post(SEED, params={"user_id": "seed-test"}).json()["data"]["count"]
    second = client.post(SEED, params={"user_id": "seed-test"}).json()["data"]["count"]
    assert first == second == 7

    # 두 번 호출 후에도 이번 달 대시보드 거래 수가 누적되지 않는다.
    today = date.today()
    ym = f"{today.year:04d}-{today.month:02d}"
    dash = client.get(
        "/api/v1/ledger/dashboard",
        params={"user_id": "seed-test", "month": ym},
    ).json()["data"]
    # seed 는 wipe 후 재삽입하므로, 이번 달 거래 수는 단일 seed 결과와 동일하다.
    assert dash["summary"]["transaction_count"] <= 7
