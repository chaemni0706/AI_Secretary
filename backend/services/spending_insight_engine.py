"""SpendingInsightEngine — briefing sentence generation.

Rule-based (template) briefings are the default. An optional LLM pass is
attempted only when a key is configured; any failure falls back to the
template. This matches the existing llm_service contract (None -> template).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services import llm_service


def _won(n: int) -> str:
    return f"{int(n):,}원"


def daily_briefing(date: str, expense_total: int, top_category: Optional[str]) -> Dict[str, str]:
    try:
        month = int(date[5:7])
        day = int(date[8:10])
        title = f"{month}월 {day}일 소비 요약"
    except (ValueError, IndexError):
        title = f"{date} 소비 요약"

    if expense_total <= 0:
        message = f"{title.replace(' 소비 요약', '')}에는 지출이 없었어요."
    else:
        message = f"{title.replace(' 소비 요약', '')}에는 총 {_won(expense_total)}을 사용했어요."
        if top_category:
            message += f" 가장 많이 쓴 분야는 {top_category}예요."

    llm = _try_llm(
        f"{date} 하루 소비 브리핑을 한 문장으로. 총지출 {expense_total}원, "
        f"최다분야 {top_category or '없음'}."
    )
    return {"title": title, "message": llm or message}


def monthly_briefing(
    month: str, category_analysis: List[Dict[str, Any]], month_expense: int
) -> Dict[str, str]:
    try:
        mm = int(month[5:7])
        title = f"{mm}월 AI 소비 브리핑"
    except (ValueError, IndexError):
        title = f"{month} AI 소비 브리핑"

    top = [c["category"] for c in category_analysis[:2]]
    if not top:
        message = "이번 달은 아직 소비 내역이 없어요."
    elif len(top) == 1:
        message = f"이번 달은 {top[0]} 소비가 가장 많았어요."
    else:
        message = f"이번 달은 {top[0]}와(과) {top[1]} 소비가 가장 많았어요."

    llm = _try_llm(
        f"{month} 월간 소비 브리핑을 한 문장으로. 총지출 {month_expense}원, "
        f"상위분야 {', '.join(top) or '없음'}."
    )
    return {"title": title, "message": llm or message}


def _try_llm(prompt: str) -> Optional[str]:
    if not llm_service.is_enabled():
        return None
    try:
        return llm_service.generate(prompt=prompt)
    except Exception:
        return None
