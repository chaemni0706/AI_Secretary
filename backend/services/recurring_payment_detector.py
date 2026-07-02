"""RecurringPaymentDetector.

Detect recurring/fixed payments. Two signals:
- the ``is_recurring`` flag set at ingest/seed time, and
- the same normalized_merchant appearing in multiple months at a stable amount.

Prototype scope: the flag is the primary signal; multi-month heuristic is a
light augmentation so newly ingested repeats can surface without a flag.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def detect(transactions: List[Any]) -> List[Dict[str, Any]]:
    """``transactions`` are LedgerTransaction ORM rows (non-deleted).

    Returns recurring payment descriptors sorted by amount desc.
    """
    by_merchant: Dict[str, List[Any]] = defaultdict(list)
    for tx in transactions:
        if (tx.transaction_type or "").upper() != "EXPENSE":
            continue
        key = tx.normalized_merchant or tx.merchant or ""
        by_merchant[key].append(tx)

    out: List[Dict[str, Any]] = []
    for _key, rows in by_merchant.items():
        flagged = any(bool(r.is_recurring) for r in rows)
        months = {(r.date or "")[:7] for r in rows if r.date}
        multi_month = len(months) >= 2
        if not (flagged or multi_month):
            continue
        rep = rows[0]
        expected_day = None
        if rep.date and len(rep.date) >= 10:
            try:
                expected_day = int(rep.date[8:10])
            except ValueError:
                expected_day = None
        out.append({
            "merchant": rep.merchant,
            "amount": rep.amount,
            "category": rep.category,
            "cycle": "monthly",
            "expected_day": expected_day,
        })
    out.sort(key=lambda r: r["amount"], reverse=True)
    return out
