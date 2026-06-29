"""Rule-based daily briefing generator (with optional LLM summary).

priority_order and key_points are always rule-based for reliability.
The `summary` sentence is produced by the LLM when a key is configured,
otherwise by a template. Never raises.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from backend.database.schema.briefing_schema import (
    BriefingSchedule,
    DailyBriefingData,
    DailyBriefingRequest,
    PriorityOrderItem,
)
from backend.services import llm_service

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "briefing_prompt.txt"
_RANK = {"high": 0, "medium": 1, "low": 2}


@lru_cache(maxsize=1)
def _priority_rules() -> dict:
    with open(_RULES_DIR / "priority_rules.json", encoding="utf-8") as f:
        return json.load(f)


def _i_ga(word: str) -> str:
    if not word:
        return "가"
    last = word[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "가"


def _eul_reul(word: str) -> str:
    if not word:
        return "를"
    last = word[-1]
    if "가" <= last <= "힣":
        return "을" if (ord(last) - 0xAC00) % 28 else "를"
    return "를"


def _to_min(hhmm: Optional[str]) -> int:
    if not hhmm:
        return 24 * 60
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        return h * 60 + m
    except ValueError:
        return 24 * 60


def _time_phrase(hhmm: Optional[str]) -> str:
    if not hhmm:
        return ""
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except ValueError:
        return ""
    ampm = "오전" if h < 12 else "오후"
    h12 = h % 12 or 12
    s = f"{ampm} {h12}시"
    return s + (f" {m}분" if m else "")


def _daypart(hhmm: Optional[str]) -> str:
    if not hhmm:
        return ""
    try:
        h = int(hhmm.split(":")[0])
    except ValueError:
        return ""
    if 5 <= h <= 11:
        return "오전"
    if 12 <= h <= 17:
        return "오후"
    if 18 <= h <= 20:
        return "저녁"
    return "밤"


def _effective_priority(title: str, category: str, given: str) -> str:
    rules = _priority_rules()
    cat = (category or "etc").lower()
    if cat in rules.get("high_categories", []):
        return "high"
    if any(kw in title for kw in rules.get("high_keywords", [])):
        return "high"
    return given or "medium"


def _schedule_reason(category: str) -> str:
    rules = _priority_rules()
    cat = (category or "etc").lower()
    return rules.get("category_reasons", {}).get(
        cat, rules.get("default_high_reason", "오늘 우선적으로 챙겨야 할 일정입니다.")
    )


def _todo_stem(title: str) -> str:
    for tail in ("챙기기", "준비하기", "하기"):
        if title.endswith(tail):
            return title[: -len(tail)].strip()
    return title.strip()


def _summary_schedule_phrase(s: BriefingSchedule) -> str:
    dp = _daypart(s.start_time)
    if not dp or s.title.startswith(dp):
        return s.title
    return f"{dp} {s.title}"


def _build_prompt(req: DailyBriefingRequest, priority_order: List[PriorityOrderItem]) -> str:
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        template = "오늘 일정을 2~3문장으로 요약하세요.\n일정:{schedules}\n할일:{todos}\n우선순위:{priority_order}"
    sched_txt = "\n".join(
        f"- {s.start_time or '시간미정'} {s.title} ({s.category}, {s.priority})" for s in req.schedules
    ) or "- 없음"
    todo_txt = "\n".join(
        f"- {t.title} ({t.priority}, {'완료' if t.is_done else '미완료'})" for t in req.todos
    ) or "- 없음"
    prio_txt = "\n".join(f"- {p.title}: {p.reason}" for p in priority_order) or "- 없음"
    return template.format(
        date=req.date, schedules=sched_txt, todos=todo_txt, priority_order=prio_txt
    )


def generate_briefing(req: DailyBriefingRequest) -> DailyBriefingData:
    schedules = sorted(req.schedules, key=lambda s: _to_min(s.start_time))
    enriched: List[Tuple[BriefingSchedule, str]] = [
        (s, _effective_priority(s.title, s.category, s.priority)) for s in schedules
    ]

    high_scheds = [s for s, p in enriched if p == "high"]
    if high_scheds:
        ordered = high_scheds
    else:
        ordered = [s for s, _ in sorted(
            enriched, key=lambda x: (_RANK.get(x[1], 1), _to_min(x[0].start_time))
        )]

    priority_order = [
        PriorityOrderItem(
            title=s.title,
            priority=_effective_priority(s.title, s.category, s.priority),
            reason=_schedule_reason(s.category),
        )
        for s in ordered
    ]

    high_todos = [t for t in req.todos if not t.is_done and (
        t.priority == "high" or any(
            kw in t.title for kw in _priority_rules().get("high_keywords", []))
    )]

    # ----- summary (template) -----
    if schedules:
        listing = ", ".join(_summary_schedule_phrase(s) for s in schedules)
        last_phrase = _summary_schedule_phrase(schedules[-1])
        template_summary = f"오늘은 {listing}{_i_ga(last_phrase)} 있습니다."
        top = ordered[0] if ordered else None
        if top is not None and (top.category or "").lower() in ("hospital", "meeting", "exam", "deadline"):
            prep = _todo_stem(high_todos[0].title) if high_todos else "준비물"
            template_summary += (
                f" {top.title} 전에는 {prep}{_eul_reul(prep)} 챙기고 "
                "이동 시간을 여유 있게 확보하는 것이 좋습니다."
            )
    else:
        template_summary = "오늘은 등록된 일정이 없습니다. 할 일에 집중하기 좋은 날입니다."

    # ----- summary (LLM, optional) -----
    llm_summary = None
    try:
        llm_summary = llm_service.generate(
            _build_prompt(req, priority_order),
            system="너는 사용자의 하루를 따뜻하고 간결하게 정리하는 한국어 비서야. 2~3문장으로만 요약해.",
        )
    except Exception:
        llm_summary = None
    summary = llm_summary if llm_summary else template_summary

    # ----- key_points (rule-based) -----
    key_points: List[str] = []
    if ordered:
        top = ordered[0]
        tp = _time_phrase(top.start_time)
        prefix = f"{tp} " if tp else ""
        key_points.append(f"{prefix}{top.title}{_i_ga(top.title)} 가장 중요한 일정입니다.")
    for t in high_todos:
        stem = _todo_stem(t.title)
        if t.title.endswith("챙기기"):
            key_points.append(f"{stem}{_eul_reul(stem)} 챙겨야 합니다.")
        else:
            key_points.append(f"'{t.title}'{_eul_reul(t.title)} 잊지 마세요.")
    for s in ordered[1:]:
        dp = _daypart(s.start_time)
        prefix = f"{dp}에는 " if dp else ""
        key_points.append(f"{prefix}{s.title}{_i_ga(s.title)} 있습니다.")

    return DailyBriefingData(
        summary=summary,
        key_points=key_points,
        priority_order=priority_order,
    )
