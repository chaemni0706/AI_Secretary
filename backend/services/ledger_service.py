"""LedgerService — the transaction boundary owner for the ledger feature.

Responsibilities:
- ingest notification / receipt parse results, classify category, and persist
- duplicate prevention (exact dedup_key + fuzzy merchant/amount/time matching)
- confirm / update / soft-delete transactions
- idempotent mock seed
- dashboard & report aggregation inputs (list helpers used by insight engines)

Dedup design:
- ``dedup_key``  : sha1 over the *canonical meaning* of the transaction
  (user, normalized_merchant, amount, transaction_type, date). Catches the
  "same notification sent twice" case AND the "notification vs receipt for the
  same purchase" case, since both reduce to the same canonical tuple.
- ``source_hash``: sha1 over the *raw input* (source_type + raw_text +
  received/captured time). Distinguishes identical re-posts for auditing.
- fuzzy pass : for near matches (±100 won, within 10 minutes) that don't share
  an exact dedup_key, we still flag a duplicate candidate.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import ledger_repository as repo
from backend.database.schema.ledger_schema import to_api_dict
from backend.services import ledger_common as common
from backend.services import merchant_category_engine as category_engine


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def ensure_user(db: Session, user_id: str) -> None:
    """Ensure a users row exists for ``user_id`` so the ledger FK is satisfied.

    The ledger owns arbitrary user_ids (e.g. 'user-1') independent of the
    planner's default 'local-user'. Idempotent; commits its own insert so the
    row is visible before the ledger insert flushes.
    """
    from backend.database.models import User  # local import avoids cycle

    if db.get(User, user_id) is None:
        ts = _now_iso()
        db.add(User(user_id=user_id, display_name=user_id,
                    created_at=ts, updated_at=ts))
        db.commit()


def _new_id() -> str:
    return f"tx_{uuid.uuid4().hex[:12]}"


def _sha1(*parts: object) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _build_dedup_key(
    *, user_id: str, normalized_merchant: str, amount: int,
    transaction_type: str, date: Optional[str],
) -> str:
    return _sha1(user_id, normalized_merchant, amount, transaction_type, date or "")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _within_minutes(a: Optional[str], b: Optional[str], minutes: int) -> bool:
    da, db_ = _parse_dt(a), _parse_dt(b)
    if da is None or db_ is None:
        return False
    return abs((da - db_).total_seconds()) <= minutes * 60


def _duplicate_payload(existing) -> Dict[str, Any]:
    return {
        "duplicate": True,
        "duplicated_transaction_id": existing.transaction_id,
        "transaction": to_api_dict(existing),
    }


def _find_duplicate(
    db: Session, *, user_id: str, dedup_key: str, normalized_merchant: str,
    amount: int, transaction_type: str, occurred_at: Optional[str],
):
    """Return an existing transaction if this is a duplicate, else None."""
    # 1) exact dedup_key
    exact = repo.find_by_dedup_key(db, user_id=user_id, dedup_key=dedup_key)
    if exact is not None:
        return exact
    # 2) fuzzy: same normalized_merchant + amount(±100), same type, ≤10 min
    for cand in repo.find_fuzzy_candidates(
        db, user_id=user_id, normalized_merchant=normalized_merchant, amount=amount
    ):
        if (cand.transaction_type or "").upper() != transaction_type.upper():
            continue
        # same-day exact merchant+amount OR within 10 minutes
        if _within_minutes(cand.occurred_at, occurred_at, 10):
            return cand
        if cand.date and occurred_at and cand.date == (occurred_at[:10]):
            return cand
    return None


def _persist_new(
    db: Session, *, user_id: str, parsed: Dict[str, Any],
    classification: Dict[str, Any], app_name: Optional[str],
    title: Optional[str], source_hash: str, dedup_key: str,
    is_recurring: bool = False, status: str = "PENDING",
    category_source_override: Optional[str] = None,
    confidence_override: Optional[float] = None,
):
    ts = _now_iso()
    tx_type = str(parsed["transaction_type"]).upper()
    needs = bool(classification.get("needs_user_confirmation", False))
    resolved_status = "NEEDS_REVIEW" if needs and status == "PENDING" else status
    tx = repo.create(
        db,
        transaction_id=_new_id(),
        user_id=user_id,
        source_type=str(parsed["source_type"]).upper(),
        app_name=app_name,
        title=title,
        raw_text=parsed.get("raw_text"),
        merchant=parsed.get("merchant"),
        normalized_merchant=parsed.get("normalized_merchant"),
        amount=int(parsed.get("amount") or 0),
        transaction_type=tx_type,
        category=classification.get("category"),
        category_source=category_source_override or classification.get("category_source"),
        confidence=confidence_override if confidence_override is not None
        else classification.get("confidence"),
        needs_user_confirmation=1 if needs else 0,
        alternatives_json=json.dumps(
            classification.get("alternatives", []), ensure_ascii=False
        ),
        occurred_at=parsed.get("occurred_at"),
        date=parsed.get("date"),
        time=parsed.get("time"),
        status=resolved_status,
        duplicated_transaction_id=None,
        dedup_key=dedup_key,
        source_hash=source_hash,
        items_json=json.dumps(parsed.get("items", []), ensure_ascii=False),
        is_recurring=1 if is_recurring else 0,
        created_at=ts,
        updated_at=ts,
    )
    return tx


# --- Public ingest entry points --------------------------------------------
def ingest_notification(
    db: Session, *, user_id: str, app_name: Optional[str], title: Optional[str],
    parsed: Dict[str, Any], received_at: Optional[str],
) -> Tuple[Dict[str, Any], bool]:
    """Persist a parsed notification. Returns (payload, is_duplicate).

    IGNORE transactions are not stored (returns a synthetic payload).
    """
    if parsed["transaction_type"] == "ignore":
        return (
            {
                "transaction_id": None,
                "source_type": "notification",
                "transaction_type": "ignore",
                "amount": parsed.get("amount", 0),
                "merchant": parsed.get("merchant"),
                "status": "ignored",
                "duplicate": False,
                "stored": False,
            },
            False,
        )

    ensure_user(db, user_id)
    normalized = parsed.get("normalized_merchant") or ""
    amount = int(parsed.get("amount") or 0)
    tx_type = parsed["transaction_type"]
    dedup_key = _build_dedup_key(
        user_id=user_id, normalized_merchant=normalized, amount=amount,
        transaction_type=tx_type, date=parsed.get("date"),
    )
    source_hash = _sha1("notification", app_name, title, parsed.get("raw_text"),
                        received_at, amount, parsed.get("merchant"))

    existing = _find_duplicate(
        db, user_id=user_id, dedup_key=dedup_key, normalized_merchant=normalized,
        amount=amount, transaction_type=tx_type, occurred_at=parsed.get("occurred_at"),
    )
    if existing is not None:
        return (_duplicate_payload(existing), True)

    classification = category_engine.classify(
        merchant=parsed.get("merchant", ""), normalized_merchant=normalized,
        transaction_type=tx_type,
    )
    tx = _persist_new(
        db, user_id=user_id, parsed=parsed, classification=classification,
        app_name=app_name, title=title, source_hash=source_hash, dedup_key=dedup_key,
    )
    return (to_api_dict(tx), False)


def ingest_receipt(
    db: Session, *, user_id: str, parsed: Dict[str, Any],
) -> Tuple[Dict[str, Any], bool]:
    """Persist a parsed receipt. Returns (payload, is_duplicate)."""
    ensure_user(db, user_id)
    normalized = parsed.get("normalized_merchant") or ""
    amount = int(parsed.get("amount") or 0)
    tx_type = parsed.get("transaction_type", "expense")
    dedup_key = _build_dedup_key(
        user_id=user_id, normalized_merchant=normalized, amount=amount,
        transaction_type=tx_type, date=parsed.get("date"),
    )
    source_hash = _sha1("receipt_scan", parsed.get("raw_text"),
                        parsed.get("occurred_at"), amount, parsed.get("merchant"))

    existing = _find_duplicate(
        db, user_id=user_id, dedup_key=dedup_key, normalized_merchant=normalized,
        amount=amount, transaction_type=tx_type, occurred_at=parsed.get("occurred_at"),
    )
    if existing is not None:
        return (_duplicate_payload(existing), True)

    classification = category_engine.classify(
        merchant=parsed.get("merchant", ""), normalized_merchant=normalized,
        transaction_type=tx_type,
    )
    # receipt-based rule hits are tagged receipt_rule when rule_based matched
    if classification.get("category_source") == "rule_based":
        classification = {**classification, "category_source": "rule_based"}
    tx = _persist_new(
        db, user_id=user_id, parsed=parsed, classification=classification,
        app_name=None, title=None, source_hash=source_hash, dedup_key=dedup_key,
    )
    return (to_api_dict(tx), False)


# --- CRUD -------------------------------------------------------------------
_STATUS_TO_DB = {
    "pending": "PENDING", "confirmed": "CONFIRMED", "duplicate": "DUPLICATE",
    "deleted": "DELETED", "needs_review": "NEEDS_REVIEW",
}


def confirm(db: Session, transaction_id: str) -> Optional[Dict[str, Any]]:
    tx = repo.update(db, transaction_id, status="CONFIRMED",
                     needs_user_confirmation=0, updated_at=_now_iso())
    return to_api_dict(tx) if tx else None


def update(
    db: Session, transaction_id: str, *, category: Optional[str] = None,
    merchant: Optional[str] = None, amount: Optional[int] = None,
    occurred_at: Optional[str] = None, status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    fields: Dict[str, Any] = {"updated_at": _now_iso()}
    if category is not None:
        # user edit -> record as user_override for future personal-rule use
        fields["category"] = category
        fields["category_source"] = "user_override"
        fields["needs_user_confirmation"] = 0
    if merchant is not None:
        fields["merchant"] = merchant
        fields["normalized_merchant"] = common.normalize_merchant(merchant)
    if amount is not None:
        fields["amount"] = int(amount)
    if occurred_at is not None:
        dt = _parse_dt(occurred_at)
        fields["occurred_at"] = occurred_at
        if dt is not None:
            fields["date"] = dt.strftime("%Y-%m-%d")
            fields["time"] = dt.strftime("%H:%M")
    if status is not None:
        fields["status"] = _STATUS_TO_DB.get(status.lower(), "PENDING")
    tx = repo.update(db, transaction_id, **fields)
    return to_api_dict(tx) if tx else None


def soft_delete(db: Session, transaction_id: str) -> bool:
    tx = repo.update(db, transaction_id, status="DELETED", updated_at=_now_iso())
    return tx is not None


def get(db: Session, transaction_id: str) -> Optional[Dict[str, Any]]:
    tx = repo.get(db, transaction_id)
    if tx is None or (tx.status or "").upper() == "DELETED":
        return None
    return to_api_dict(tx)


# --- Idempotent seed --------------------------------------------------------
def _day_in_month(base: date, day: int) -> date:
    """Return ``day`` within base's month, clamped to the month's last day.

    Non-existent days (e.g. Feb 30) are corrected via ``calendar.monthrange``.
    """
    last = calendar.monthrange(base.year, base.month)[1]
    return date(base.year, base.month, min(day, last))


def build_seed_rows(base_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Build the sample seed rows relative to ``base_date`` (default today).

    Dates are distributed naturally within the current month (plus 'yesterday'),
    so the demo always matches the month being viewed. Field shape is identical
    to the previous static rows; only ``occurred_at`` is computed.
    """
    base = base_date or date.today()
    yesterday = base - timedelta(days=1)

    def iso(d: date, hhmm: str) -> str:
        return f"{d.isoformat()}T{hhmm}:00"

    return [
        {"merchant": "스타벅스 강남역점", "amount": 5800, "transaction_type": "expense",
         "category": "카페", "occurred_at": iso(base, "14:20"),
         "category_source": "rule_based"},
        {"merchant": "홍콩반점0410 강남역점", "amount": 9500, "transaction_type": "expense",
         "category": "식비", "occurred_at": iso(yesterday, "12:30"),
         "category_source": "mock_place_search"},
        {"merchant": "카카오T", "amount": 12000, "transaction_type": "expense",
         "category": "교통", "occurred_at": iso(_day_in_month(base, 3), "09:10"),
         "category_source": "rule_based"},
        {"merchant": "더현대서울", "amount": 18000, "transaction_type": "expense",
         "category": "쇼핑", "occurred_at": iso(_day_in_month(base, 8), "16:30"),
         "category_source": "mock_place_search", "confidence": 0.68,
         "needs_user_confirmation": True},
        {"merchant": "NETFLIX", "amount": 17000, "transaction_type": "expense",
         "category": "구독_콘텐츠", "occurred_at": iso(_day_in_month(base, 10), "08:00"),
         "category_source": "rule_based", "is_recurring": True},
        {"merchant": "KT 통신비", "amount": 69000, "transaction_type": "expense",
         "category": "통신_공과금", "occurred_at": iso(_day_in_month(base, 15), "08:00"),
         "category_source": "mock_place_search", "is_recurring": True},
        {"merchant": "급여", "amount": 500000, "transaction_type": "income",
         "category": "수입", "occurred_at": iso(_day_in_month(base, 20), "09:00"),
         "category_source": "notification_rule"},
    ]


def seed(db: Session, *, user_id: str) -> List[Dict[str, Any]]:
    """Idempotent: wipe this user's ledger rows, then reinsert the sample set."""
    ensure_user(db, user_id)
    repo.delete_all_for_user(db, user_id=user_id)
    ts = _now_iso()
    out: List[Dict[str, Any]] = []
    for row in build_seed_rows():
        occurred = row["occurred_at"]
        dt = _parse_dt(occurred)
        date = dt.strftime("%Y-%m-%d") if dt else None
        time = dt.strftime("%H:%M") if dt else None
        needs = bool(row.get("needs_user_confirmation", False))
        merchant = row["merchant"]
        normalized = common.normalize_merchant(merchant)
        tx_type = row["transaction_type"]
        amount = int(row["amount"])
        dedup_key = _build_dedup_key(
            user_id=user_id, normalized_merchant=normalized, amount=amount,
            transaction_type=tx_type, date=date,
        )
        tx = repo.create(
            db,
            transaction_id=_new_id(),
            user_id=user_id,
            source_type="SEED",
            app_name=None,
            title=None,
            raw_text=None,
            merchant=merchant,
            normalized_merchant=normalized,
            amount=amount,
            transaction_type=tx_type.upper(),
            category=row["category"],
            category_source=row.get("category_source", "rule_based"),
            confidence=row.get("confidence", 0.9),
            needs_user_confirmation=1 if needs else 0,
            alternatives_json=json.dumps([], ensure_ascii=False),
            occurred_at=occurred,
            date=date,
            time=time,
            status="NEEDS_REVIEW" if needs else "CONFIRMED",
            duplicated_transaction_id=None,
            dedup_key=dedup_key,
            source_hash=_sha1("seed", merchant, amount, occurred),
            items_json=json.dumps([], ensure_ascii=False),
            is_recurring=1 if row.get("is_recurring") else 0,
            created_at=ts,
            updated_at=ts,
        )
        out.append(to_api_dict(tx))
    return out
