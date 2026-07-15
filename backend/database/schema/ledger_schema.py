"""Ledger request/response schemas.

DB stores UPPERCASE enums (EXPENSE / PENDING / ...); the API contract with the
Flutter frontend uses lowercase (expense / pending / ...). ``to_api_dict``
performs that translation on the way out. Date -> 'YYYY-MM-DD',
Time -> 'HH:MM', amount -> integer won (shared common_schema conventions).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Requests ---------------------------------------------------------------
class NotificationSimulateRequest(BaseModel):
    user_id: str
    app_name: Optional[str] = None
    title: Optional[str] = ""
    body: str = ""
    received_at: Optional[str] = Field(None, description="'YYYY-MM-DDTHH:MM:SS'")


class ReceiptScanRequest(BaseModel):
    user_id: str
    receipt_text: str
    captured_at: Optional[str] = Field(None, description="'YYYY-MM-DDTHH:MM:SS'")


class TransactionUpdateRequest(BaseModel):
    category: Optional[str] = None
    merchant: Optional[str] = None
    amount: Optional[int] = None
    occurred_at: Optional[str] = None
    status: Optional[str] = Field(
        None, description="pending|confirmed|duplicate|deleted|needs_review"
    )
    memo: Optional[str] = Field(None, description="사용자 자유 메모(빈 문자열이면 메모 삭제)")


# --- Serialization ----------------------------------------------------------
def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def to_api_dict(tx) -> Dict[str, Any]:
    """Convert a LedgerTransaction ORM row to the lowercase API dict."""
    return {
        "transaction_id": tx.transaction_id,
        "user_id": tx.user_id,
        "source_type": (tx.source_type or "").lower(),
        "app_name": tx.app_name,
        "title": tx.title,
        "raw_text": tx.raw_text,
        "merchant": tx.merchant,
        "normalized_merchant": tx.normalized_merchant,
        "amount": tx.amount,
        "transaction_type": (tx.transaction_type or "").lower(),
        "category": tx.category,
        "category_source": tx.category_source,
        "confidence": tx.confidence,
        "needs_user_confirmation": bool(tx.needs_user_confirmation),
        "alternatives": _loads(tx.alternatives_json, []),
        "occurred_at": tx.occurred_at,
        "date": tx.date,
        "time": tx.time,
        "status": (tx.status or "").lower(),
        "duplicate": (tx.status or "").upper() == "DUPLICATE",
        "duplicated_transaction_id": tx.duplicated_transaction_id,
        "items": _loads(tx.items_json, []),
        "is_recurring": bool(tx.is_recurring),
        "memo": tx.memo,
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
    }
