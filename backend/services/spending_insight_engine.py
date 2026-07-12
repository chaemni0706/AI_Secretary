"""SpendingInsightEngine — briefing sentence generation.

Rule-based (template) briefings are returned immediately. When an LLM key is
configured, the AI sentence is generated in the BACKGROUND and cached; the
endpoint never blocks on the network call. Responses include a `pending` flag
so the client can re-fetch shortly to pick up the AI sentence once ready.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from backend.services import llm_service

# LLM 브리핑 결과 캐시(프롬프트 -> 문장). 매 요청마다 OpenAI 를 호출하면 2~5초가
# 걸리므로 결과를 캐시하고, 생성은 '백그라운드'로만 한다. 엔드포인트는 LLM 호출을
# 절대 기다리지 않고 즉시 템플릿 문장을 반환한다(pending=True). 준비되면 다음
# 조회에서 캐시된 AI 문장을 반환한다(pending=False).
_LLM_CACHE: "OrderedDict[str, str]" = OrderedDict()
_LLM_CACHE_MAX = 256
_INFLIGHT: set = set()
_LOCK = threading.Lock()


def clear_briefing_cache() -> None:
    """거래 변경 등으로 캐시를 강제로 비워야 할 때 호출한다(선택)."""
    with _LOCK:
        _LLM_CACHE.clear()
        _INFLIGHT.clear()


def _won(n: int) -> str:
    return f"{int(n):,}원"


def _cache_get(prompt: str) -> Optional[str]:
    with _LOCK:
        val = _LLM_CACHE.get(prompt)
        if val is not None:
            _LLM_CACHE.move_to_end(prompt)
        return val


def _cache_put(prompt: str, val: str) -> None:
    with _LOCK:
        _LLM_CACHE[prompt] = val
        _LLM_CACHE.move_to_end(prompt)
        while len(_LLM_CACHE) > _LLM_CACHE_MAX:
            _LLM_CACHE.popitem(last=False)


def _generate_in_background(prompt: str) -> None:
    try:
        result = llm_service.generate(prompt=prompt)
    except Exception:
        result = None
    if result:
        _cache_put(prompt, result)
    with _LOCK:
        _INFLIGHT.discard(prompt)


def _ai_or_pending(prompt: str) -> Tuple[Optional[str], bool]:
    """(ai_message, pending) 반환.

    - LLM 비활성: (None, False) → 호출부는 템플릿 사용, pending 아님
    - 캐시 있음:  (문장, False)
    - 캐시 없음:  백그라운드 생성 시작 후 (None, True)
    """
    if not llm_service.is_enabled():
        return None, False
    cached = _cache_get(prompt)
    if cached is not None:
        return cached, False
    with _LOCK:
        should_start = prompt not in _INFLIGHT
        if should_start:
            _INFLIGHT.add(prompt)
    if should_start:
        threading.Thread(
            target=_generate_in_background, args=(prompt,), daemon=True
        ).start()
    return None, True


def daily_briefing(date: str, expense_total: int, top_category: Optional[str]) -> Dict[str, Any]:
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

    ai, pending = _ai_or_pending(
        f"{date} 하루 소비 브리핑을 한 문장으로. 총지출 {expense_total}원, "
        f"최다분야 {top_category or '없음'}."
    )
    return {"title": title, "message": ai or message, "pending": pending}


def monthly_briefing(
    month: str, category_analysis: List[Dict[str, Any]], month_expense: int
) -> Dict[str, Any]:
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

    ai, pending = _ai_or_pending(
        f"{month} 월간 소비 브리핑을 한 문장으로. 총지출 {month_expense}원, "
        f"상위분야 {', '.join(top) or '없음'}."
    )
    return {"title": title, "message": ai or message, "pending": pending}
