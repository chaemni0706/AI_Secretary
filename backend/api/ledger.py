"""AI 가계부 (ledger) API endpoints.

Prefix-free paths; ``main.py`` mounts this router under settings.API_V1_PREFIX
(/api/v1), so live paths are /api/v1/ledger/... . Common {success, message,
data} envelope preserved via success_response.

Prototype boundaries (NOT implemented on purpose): real SMS permission, Android
NotificationListener, real card/bank APIs, real Naver/Kakao place search, and a
hard OCR dependency. Notifications are mock POSTs, place search is mock JSON,
and OCR is optional with a safe fallback.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database import ledger_repository as repo
from backend.database.schema.ledger_schema import (
    NotificationSimulateRequest,
    ReceiptScanRequest,
    TransactionUpdateRequest,
    to_api_dict,
)
from backend.database.session import get_db
from backend.services import (
    budget_alert_service,
    ledger_notification_parser,
    ledger_service,
    receipt_ocr_service,
    receipt_parser,
    recurring_payment_detector,
    spending_insight_engine,
)

router = APIRouter(tags=["ledger"])

_DEFAULT_USER = "user-1"


# --- 7-1 notification simulate ---------------------------------------------
@router.post("/ledger/notifications/simulate", summary="mock 알림 파싱/거래 생성")
def simulate_notification(
    req: NotificationSimulateRequest, db: Session = Depends(get_db)
):
    parsed = ledger_notification_parser.parse(
        app_name=req.app_name or "",
        title=req.title or "",
        body=req.body or "",
        received_at=req.received_at,
    )
    payload, is_dup = ledger_service.ingest_notification(
        db, user_id=req.user_id, app_name=req.app_name, title=req.title,
        parsed=parsed, received_at=req.received_at,
    )
    db.commit()
    if is_dup:
        return success_response(
            message="이미 등록된 거래로 판단되어 기존 거래를 반환합니다.", data=payload
        )
    if not payload.get("stored", True):
        return success_response(message="광고/안내 알림으로 판단되어 저장하지 않았습니다.", data=payload)
    return success_response(message="거래 알림을 분석했습니다.", data=payload)


# --- 7-2 receipt scan (JSON receipt_text) ----------------------------------
@router.post("/ledger/receipts/scan", summary="영수증 텍스트 스캔/파싱")
def scan_receipt(req: ReceiptScanRequest, db: Session = Depends(get_db)):
    parsed = receipt_parser.parse(
        receipt_text=req.receipt_text, captured_at=req.captured_at
    )
    payload, is_dup = ledger_service.ingest_receipt(
        db, user_id=req.user_id, parsed=parsed
    )
    db.commit()
    if is_dup:
        return success_response(
            message="이미 등록된 거래로 판단되어 기존 거래를 반환합니다.", data=payload
        )
    return success_response(message="영수증을 분석했습니다.", data=payload)


# --- 7-2b receipt scan (multipart image upload; OCR optional) --------------
@router.post("/ledger/receipts/scan-image", summary="영수증 이미지 업로드(OCR optional)")
async def scan_receipt_image(
    user_id: str = Form(...),
    captured_at: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Read bytes defensively; never 500 on a bad/empty upload.
    try:
        image_bytes = await file.read()
    except Exception:
        image_bytes = b""

    text = receipt_ocr_service.extract_text(image_bytes)
    if not text:
        # Safe fallback: OCR unavailable -> needs_review, nothing stored.
        return success_response(
            message="OCR 엔진을 사용할 수 없어 검토가 필요합니다. receipt_text로 다시 시도해주세요.",
            data={
                "transaction_id": None,
                "source_type": "receipt_scan",
                "status": "needs_review",
                "ocr_available": receipt_ocr_service.is_available(),
                "duplicate": False,
                "stored": False,
                "filename": file.filename,
            },
        )
    parsed = receipt_parser.parse(receipt_text=text, captured_at=captured_at)
    payload, is_dup = ledger_service.ingest_receipt(db, user_id=user_id, parsed=parsed)
    db.commit()
    msg = ("이미 등록된 거래로 판단되어 기존 거래를 반환합니다." if is_dup
           else "영수증 이미지를 분석했습니다.")
    return success_response(message=msg, data=payload)


# --- aggregation helpers ----------------------------------------------------
def _income_expense_split(rows) -> Dict[str, int]:
    exp = sum(r.amount for r in rows if (r.transaction_type or "").upper() == "EXPENSE")
    inc = sum(r.amount for r in rows if (r.transaction_type or "").upper() == "INCOME")
    return {"expense": exp, "income": inc}


def _spent_by_category(rows) -> Dict[str, int]:
    acc: Dict[str, int] = defaultdict(int)
    for r in rows:
        if (r.transaction_type or "").upper() == "EXPENSE" and r.category:
            acc[r.category] += r.amount
    return dict(acc)


# --- 7-3 dashboard ----------------------------------------------------------
@router.get("/ledger/dashboard", summary="가계부 홈 대시보드")
def dashboard(
    user_id: str = Query(...),
    month: str = Query(..., description="'YYYY-MM'"),
    selected_date: Optional[str] = Query(None, description="'YYYY-MM-DD'"),
    db: Session = Depends(get_db),
):
    month_rows = repo.list_by_month(db, user_id=user_id, month=month)
    split = _income_expense_split(month_rows)
    spent_cat = _spent_by_category(month_rows)
    top_category = max(spent_cat, key=spent_cat.get) if spent_cat else None

    # calendar: per-day aggregates
    by_date: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"expense_total": 0, "income_total": 0, "transaction_count": 0}
    )
    for r in month_rows:
        if not r.date:
            continue
        d = by_date[r.date]
        if (r.transaction_type or "").upper() == "EXPENSE":
            d["expense_total"] += r.amount
        elif (r.transaction_type or "").upper() == "INCOME":
            d["income_total"] += r.amount
        d["transaction_count"] += 1
    calendar = [
        {
            "date": d,
            "expense_total": v["expense_total"],
            "income_total": v["income_total"],
            "net_total": v["income_total"] - v["expense_total"],
            "transaction_count": v["transaction_count"],
        }
        for d, v in sorted(by_date.items())
    ]

    # today's expense == selected_date if provided else nothing
    sel = selected_date
    sel_rows = repo.list_by_date(db, user_id=user_id, date=sel) if sel else []
    sel_split = _income_expense_split(sel_rows)
    sel_spent_cat = _spent_by_category(sel_rows)
    sel_top = max(sel_spent_cat, key=sel_spent_cat.get) if sel_spent_cat else None
    briefing = spending_insight_engine.daily_briefing(
        sel or month, sel_split["expense"], sel_top
    ) if sel else spending_insight_engine.daily_briefing(month, 0, None)

    pending = [to_api_dict(r) for r in repo.list_pending(db, user_id=user_id)]
    alerts = budget_alert_service.budget_alerts(spent_cat)
    recurring = recurring_payment_detector.detect(month_rows)

    data = {
        "summary": {
            "today_expense": sel_split["expense"],
            "month_expense": split["expense"],
            "month_income": split["income"],
            "balance": split["income"] - split["expense"],
            "transaction_count": len(month_rows),
            "top_category": top_category,
        },
        "calendar": calendar,
        "selected_date": {
            "date": sel,
            "expense_total": sel_split["expense"],
            "income_total": sel_split["income"],
            "briefing": briefing,
            "transactions": [to_api_dict(r) for r in sel_rows],
        },
        "pending_transactions": pending,
        "budget_alerts": alerts,
        "recurring_preview": recurring[:3],
    }
    return success_response(message="가계부 대시보드입니다.", data=data)


# --- 7-4 report -------------------------------------------------------------
@router.get("/ledger/report", summary="월간 소비 리포트")
def report(
    user_id: str = Query(...),
    month: str = Query(..., description="'YYYY-MM'"),
    db: Session = Depends(get_db),
):
    rows = repo.list_by_month(db, user_id=user_id, month=month)
    split = _income_expense_split(rows)
    spent_cat = _spent_by_category(rows)
    total_expense = split["expense"]

    category_analysis = [
        {
            "category": cat,
            "amount": amt,
            "ratio": round(amt / total_expense * 100) if total_expense else 0,
        }
        for cat, amt in sorted(spent_cat.items(), key=lambda kv: kv[1], reverse=True)
    ]
    budget_usage = budget_alert_service.compute_budget_usage(spent_cat)
    recurring = recurring_payment_detector.detect(rows)
    briefing = spending_insight_engine.monthly_briefing(
        month, category_analysis, total_expense
    )

    data = {
        "month": month,
        "summary": {
            "month_expense": split["expense"],
            "month_income": split["income"],
            "balance": split["income"] - split["expense"],
        },
        "category_analysis": category_analysis,
        "budget_usage": budget_usage,
        "recurring_payments": recurring,
        "briefing": briefing,
    }
    return success_response(message="월간 소비 리포트입니다.", data=data)


# --- 7-5 confirm ------------------------------------------------------------
@router.post("/ledger/transactions/{transaction_id}/confirm", summary="거래 확정")
def confirm_transaction(transaction_id: str, db: Session = Depends(get_db)):
    data = ledger_service.confirm(db, transaction_id)
    if data is None:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    db.commit()
    return success_response(message="거래를 확정했습니다.", data=data)


# --- 7-6 update -------------------------------------------------------------
@router.patch("/ledger/transactions/{transaction_id}", summary="거래 수정")
def update_transaction(
    transaction_id: str, payload: TransactionUpdateRequest,
    db: Session = Depends(get_db),
):
    data = ledger_service.update(
        db, transaction_id, category=payload.category, merchant=payload.merchant,
        amount=payload.amount, occurred_at=payload.occurred_at, status=payload.status,
    )
    if data is None:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    db.commit()
    return success_response(message="거래를 수정했습니다.", data=data)


# --- 7-7 delete (soft) ------------------------------------------------------
@router.delete("/ledger/transactions/{transaction_id}", summary="거래 삭제(soft)")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    ok = ledger_service.soft_delete(db, transaction_id)
    if not ok:
        raise HTTPException(status_code=404, detail="거래를 찾을 수 없습니다.")
    db.commit()
    return success_response(
        message="거래를 삭제했습니다.", data={"transaction_id": transaction_id, "deleted": True}
    )


# --- 7-8 mock seed ----------------------------------------------------------
@router.post("/ledger/mock/seed", summary="mock 데이터 시드(idempotent)")
def mock_seed(user_id: str = Query(_DEFAULT_USER), db: Session = Depends(get_db)):
    rows = ledger_service.seed(db, user_id=user_id)
    db.commit()
    return success_response(
        message="시연용 mock 거래를 생성했습니다.",
        data={"user_id": user_id, "count": len(rows), "transactions": rows},
    )
