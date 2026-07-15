"""ReceiptParser.

Rule-based parsing of receipt OCR text into transaction fields. This is the
MVP core (image OCR is optional — see receipt_ocr_service). No external OCR
dependency here.

Extraction strategy:
- merchant: first non-empty line (receipts put the store name at the top).
- amount: prefer the value near a total keyword (합계/총액/결제금액/받을금액);
  otherwise the largest amount on the receipt.
- occurred_at/date/time: from a date/time line if present, else captured_at.
- items: lines that look like "<name> <amount>" excluding total lines.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from backend.services import ledger_common as common

_TOTAL_KEYWORDS = ("합계", "총액", "결제금액", "받을금액", "총결제", "합 계")
_ITEM_AMOUNT_RE = re.compile(r"^(?P<name>.+?)\s+(?P<amt>\d{1,3}(?:,\d{3})+|\d{3,})\s*원?$")
_DATE_RE = re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def _clean_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _extract_merchant(lines: List[str]) -> str:
    return lines[0] if lines else ""


def _extract_datetime(
    lines: List[str], captured_at: Optional[str]
) -> Dict[str, Optional[str]]:
    joined = " ".join(lines)
    dm = _DATE_RE.search(joined)
    tm = _TIME_RE.search(joined)
    if dm:
        y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        hh, mm = (int(tm.group(1)), int(tm.group(2))) if tm else (0, 0)
        try:
            dt = datetime(y, mo, d, hh, mm)
            return {
                "occurred_at": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"),
            }
        except ValueError:
            pass
    # fall back to captured_at
    if captured_at:
        try:
            dt = datetime.fromisoformat(captured_at)
            return {
                "occurred_at": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M"),
            }
        except ValueError:
            return {"occurred_at": captured_at, "date": None, "time": None}
    return {"occurred_at": None, "date": None, "time": None}


def _extract_amount(lines: List[str]) -> int:
    # 1) amount on a line containing a total keyword
    for ln in lines:
        if any(k in ln for k in _TOTAL_KEYWORDS):
            amts = common.extract_amounts(ln)
            if amts:
                return max(amts)
    # 2) fallback: largest amount anywhere
    all_amts = common.extract_amounts(" ".join(lines))
    return max(all_amts) if all_amts else 0


def _extract_items(lines: List[str]) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    for ln in lines:
        if any(k in ln for k in _TOTAL_KEYWORDS):
            continue
        m = _ITEM_AMOUNT_RE.match(ln)
        if not m:
            continue
        name = m.group("name").strip()
        # skip lines that are just a date/time or payment method
        if _DATE_RE.search(name) or not name:
            continue
        amt = int(m.group("amt").replace(",", ""))
        items.append({"name": name, "amount": amt})
    return items


def parse(
    *, receipt_text: str, captured_at: Optional[str] = None
) -> Dict[str, object]:
    """Parse receipt text into transaction fields (lowercase enums)."""
    lines = _clean_lines(receipt_text)
    merchant = _extract_merchant(lines)
    when = _extract_datetime(lines, captured_at)
    amount = _extract_amount(lines)
    items = _extract_items(lines)

    return {
        "transaction_type": "expense",
        "amount": amount,
        "merchant": merchant,
        "normalized_merchant": common.normalize_merchant(merchant),
        "occurred_at": when["occurred_at"],
        "date": when["date"],
        "time": when["time"],
        "raw_text": receipt_text or "",
        "source_type": "receipt_scan",
        "items": items,
    }
