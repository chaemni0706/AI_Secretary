"""Data-access layer for ``ledger_transactions``.

Kept separate from ``repository.py`` (planner domain) so the planner data-access
contract is not touched. Pure persistence helpers on a passed-in Session; they
``flush`` but do NOT ``commit`` — the service layer owns the transaction
boundary (same convention as ``repository.py``).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.ledger_models import LedgerTransaction


def create(db: Session, **fields) -> LedgerTransaction:
    tx = LedgerTransaction(**fields)
    db.add(tx)
    db.flush()
    return tx


def get(db: Session, transaction_id: str) -> Optional[LedgerTransaction]:
    return db.get(LedgerTransaction, transaction_id)


def update(db: Session, transaction_id: str, **fields) -> Optional[LedgerTransaction]:
    tx = db.get(LedgerTransaction, transaction_id)
    if tx is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(tx, key):
            setattr(tx, key, value)
    db.flush()
    return tx


def find_by_dedup_key(
    db: Session, *, user_id: str, dedup_key: str
) -> Optional[LedgerTransaction]:
    """Exact-match dedup lookup (excludes DELETED)."""
    if not dedup_key:
        return None
    stmt = (
        select(LedgerTransaction)
        .where(
            LedgerTransaction.user_id == user_id,
            LedgerTransaction.dedup_key == dedup_key,
            LedgerTransaction.status != "DELETED",
        )
        .order_by(LedgerTransaction.created_at)
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def find_fuzzy_candidates(
    db: Session, *, user_id: str, normalized_merchant: str, amount: int
) -> List[LedgerTransaction]:
    """Return candidate rows sharing normalized_merchant and amount within
    ±100 won (final time/type check done by the service)."""
    lo, hi = max(0, amount - 100), amount + 100
    stmt = (
        select(LedgerTransaction)
        .where(
            LedgerTransaction.user_id == user_id,
            LedgerTransaction.normalized_merchant == normalized_merchant,
            LedgerTransaction.amount >= lo,
            LedgerTransaction.amount <= hi,
            LedgerTransaction.status != "DELETED",
        )
        .order_by(LedgerTransaction.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def list_by_month(
    db: Session, *, user_id: str, month: str, include_deleted: bool = False
) -> List[LedgerTransaction]:
    """List transactions whose ``date`` starts with ``month`` ('YYYY-MM')."""
    stmt = select(LedgerTransaction).where(
        LedgerTransaction.user_id == user_id,
        LedgerTransaction.date.like(f"{month}%"),
    )
    if not include_deleted:
        stmt = stmt.where(LedgerTransaction.status != "DELETED")
    stmt = stmt.order_by(LedgerTransaction.occurred_at)
    return list(db.execute(stmt).scalars().all())


def list_by_date(
    db: Session, *, user_id: str, date: str, include_deleted: bool = False
) -> List[LedgerTransaction]:
    stmt = select(LedgerTransaction).where(
        LedgerTransaction.user_id == user_id,
        LedgerTransaction.date == date,
    )
    if not include_deleted:
        stmt = stmt.where(LedgerTransaction.status != "DELETED")
    stmt = stmt.order_by(LedgerTransaction.occurred_at)
    return list(db.execute(stmt).scalars().all())


def list_pending(db: Session, *, user_id: str) -> List[LedgerTransaction]:
    stmt = (
        select(LedgerTransaction)
        .where(
            LedgerTransaction.user_id == user_id,
            LedgerTransaction.status == "PENDING",
        )
        .order_by(LedgerTransaction.occurred_at)
    )
    return list(db.execute(stmt).scalars().all())


def list_all(
    db: Session, *, user_id: str, include_deleted: bool = False
) -> List[LedgerTransaction]:
    stmt = select(LedgerTransaction).where(LedgerTransaction.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(LedgerTransaction.status != "DELETED")
    stmt = stmt.order_by(LedgerTransaction.occurred_at)
    return list(db.execute(stmt).scalars().all())


def delete_all_for_user(db: Session, *, user_id: str) -> int:
    """Hard-delete every ledger row for a user (used by idempotent seed)."""
    rows = db.execute(
        select(LedgerTransaction).where(LedgerTransaction.user_id == user_id)
    ).scalars().all()
    count = 0
    for row in rows:
        db.delete(row)
        count += 1
    db.flush()
    return count
