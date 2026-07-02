"""LedgerNotificationParser.

Parse a mock payment/deposit notification (app_name / title / body /
received_at) into structured transaction fields. Rule-based only, driven by
``rules/ledger_notification_rules.json`` with an in-code fallback.

No real SMS / Android NotificationListener / financial API is involved — the
prototype receives mock notifications via the API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from backend.services import ledger_common as common


def _classify_type(title: str, body: str) -> str:
    """Return one of expense / income / cancel / ignore.

    Precedence: cancel > ignore > income > expense. Cancel wins so a
    "결제취소" is never mistaken for an expense; ignore filters ads/coupons
    before they can match a stray income/expense keyword.
    """
    rules = common.load_notification_rules()
    text = f"{title} {body}"

    def has_any(keys) -> bool:
        return any(k in text for k in keys)

    if has_any(rules.get("cancel_keywords", [])):
        return "cancel"
    if has_any(rules.get("ignore_keywords", [])):
        return "ignore"
    if has_any(rules.get("income_keywords", [])):
        return "income"
    if has_any(rules.get("expense_keywords", [])):
        return "expense"
    return "ignore"


def _split_datetime(received_at: Optional[str]) -> Dict[str, Optional[str]]:
    """Split an ISO datetime into occurred_at / date / time."""
    if not received_at:
        return {"occurred_at": None, "date": None, "time": None}
    try:
        dt = datetime.fromisoformat(received_at)
    except ValueError:
        return {"occurred_at": received_at, "date": None, "time": None}
    return {
        "occurred_at": dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M"),
    }


def parse(
    *,
    app_name: str,
    title: str,
    body: str,
    received_at: Optional[str],
) -> Dict[str, object]:
    """Parse a notification into transaction fields (lowercase enums)."""
    tx_type = _classify_type(title or "", body or "")
    amount = common.extract_first_amount(body or "")
    merchant = common.extract_merchant_from_notification(body or "")
    when = _split_datetime(received_at)

    return {
        "transaction_type": tx_type,
        "amount": amount,
        "merchant": merchant,
        "normalized_merchant": common.normalize_merchant(merchant),
        "occurred_at": when["occurred_at"],
        "date": when["date"],
        "time": when["time"],
        "raw_text": body or "",
        "source_type": "notification",
    }
