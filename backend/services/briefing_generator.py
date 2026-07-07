"""Rule-based daily briefing generator (with optional LLM summary).

priority_order and key_points are always rule-based for reliability.
The summary sentence is produced by the LLM when a key is configured,
otherwise by a template. Never raises.

Importance judgement (which schedules/to-dos are "high") stays in
``priority_rules.json``. Briefing *phrasing* — dayparts, summary / key-point
templates and to-do stem suffixes — lives in ``briefing_rules.json`` so wording
can be tuned without code changes. If ``briefing_rules.json`` is missing or
corrupt, a built-in default (identical to the previous hard-coded behaviour)
is used so the endpoint never breaks.
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
from backend.services import tts_response_builder, user_preference_service

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "briefing_prompt.txt"

_RANK = {"high": 0, "medium": 1, "low": 2}

# Built-in fallback — mirrors the original hard-coded policy exactly, so a
# missing/corrupt briefing_rules.json produces identical output.
DEFAULT_BRIEFING_RULES: dict = {
    "schema_version": 1,
    "daypart_rules": [
        {"label": "오전", "start_hour": 5, "end_hour": 11},
        {"label": "오후", "start_hour": 12, "end_hour": 17},
        {"label": "저녁", "start_hour": 18, "end_hour": 20},
    ],
    "daypart_default": "밤",
    "important_tip_categories": ["hospital", "meeting", "exam", "deadline"],
    "todo_stem_suffixes": ["챙기기", "준비하기", "하기"],
    "default_prep_word": "준비물",
    "summary_templates": {
        "has_schedules": "오늘은 {listing}{subject_particle} 있습니다.",
        "no_schedules": "오늘은 등록된 일정이 없습니다. 할 일에 집중하기 좋은 날입니다.",
        "prep_tip": " {top_title} 전에는 {prep}{object_particle} 챙기고 이동 시간을 여유 있게 확보하는 것이 좋습니다.",
    },
    "key_point_templates": {
        "top_schedule": "{time_prefix}{title}{subject_particle} 가장 중요한 일정입니다.",
        "todo_checklist": "{stem}{object_particle} 챙겨야 합니다.",
        "todo_reminder": "'{title}'{object_particle} 잊지 마세요.",
        "other_schedule": "{daypart_prefix}{title}{subject_particle} 있습니다.",
    },
    "todo_checklist_suffix": "챙기기",
    "other_schedule_daypart_suffix": "에는 ",
    "limits": {"max_key_points": 5},
}


@lru_cache(maxsize=1)
def _priority_rules() -> dict:
    # Unchanged: importance judgement source of truth.
    with open(_RULES_DIR / "priority_rules.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _briefing_rules() -> dict:
    """Load briefing phrasing rules; fall back to the built-in default so the
    generator never raises on a missing/corrupt file."""
    try:
        with open(_RULES_DIR / "briefing_rules.json", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return DEFAULT_BRIEFING_RULES
    # Shallow-merge over defaults so a partial file still works.
    merged = dict(DEFAULT_BRIEFING_RULES)
    merged.update(data)
    return merged


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
    """Time-of-day label driven by briefing_rules.daypart_rules.

    Ranges may wrap past midnight (end_hour < start_hour). Anything not covered
    by a rule gets daypart_default.
    """
    if not hhmm:
        return ""
    try:
        h = int(hhmm.split(":")[0])
    except ValueError:
        return ""
    rules = _briefing_rules()
    for r in rules.get("daypart_rules", []):
        start, end = r["start_hour"], r["end_hour"]
        if start <= end:
            if start <= h <= end:
                return r["label"]
        else:  # wraps midnight, e.g. 21..4
            if h >= start or h <= end:
                return r["label"]
    return rules.get("daypart_default", "밤")


def _effective_priority(title: str, category: str, given: str) -> str:
    rules = _priority_rules()
    cat = (category or "etc").lower()
    if cat in rules.get("high_categories", []):
        return "high"
    keywords = list(rules.get("high_keywords", [])) + list(
        rules.get("briefing_high_keywords", [])
    )
    if any(kw in title for kw in keywords):
        return "high"
    return given or "medium"


def _schedule_reason(category: str) -> str:
    rules = _priority_rules()
    cat = (category or "etc").lower()
    return rules.get("category_reasons", {}).get(
        cat, rules.get("default_high_reason", "오늘 우선적으로 챙겨야 할 일정입니다.")
    )


def _todo_stem(title: str) -> str:
    for tail in _briefing_rules().get("todo_stem_suffixes", []):
        if title.endswith(tail):
            return title[: -len(tail)].strip()
    return title.strip()


def _summary_schedule_phrase(s: BriefingSchedule) -> str:
    dp = _daypart(s.start_time)
    if not dp or s.title.startswith(dp):
        return s.title
    return f"{dp} {s.title}"


def _build_prompt(req: DailyBriefingRequest,
                  priority_order: List[PriorityOrderItem]) -> str:
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        template = "오늘 일정을 2~3문장으로 요약하세요.\n일정:{schedules}\n할일:{todos}\n우선순위:{priority_order}"
    sched_txt = "\n".join(
        f"- {s.start_time or '시간미정'} {s.title} ({s.category}, {s.priority})"
        for s in req.schedules
    ) or "- 없음"
    todo_txt = "\n".join(
        f"- {t.title} ({t.priority}, {'완료' if t.is_done else '미완료'})"
        for t in req.todos
    ) or "- 없음"
    prio_txt = "\n".join(f"- {p.title}: {p.reason}" for p in priority_order) or "- 없음"
    return template.format(
        date=req.date, schedules=sched_txt, todos=todo_txt, priority_order=prio_txt
    )


def generate_briefing(req: DailyBriefingRequest, preferences: Optional[dict] = None) -> DailyBriefingData:
    brules = _briefing_rules()
    s_tpl = brules["summary_templates"]
    k_tpl = brules["key_point_templates"]
    tip_cats = tuple(brules.get("important_tip_categories", []))
    checklist_suffix = brules.get("todo_checklist_suffix", "챙기기")
    daypart_suffix = brules.get("other_schedule_daypart_suffix", "에는 ")
    max_kp = brules.get("limits", {}).get("max_key_points")

    schedules = sorted(req.schedules, key=lambda s: _to_min(s.start_time))
    enriched: List[Tuple[BriefingSchedule, str]] = [
        (s, _effective_priority(s.title, s.category, s.priority)) for s in schedules
    ]
    ordered_pairs = sorted(
        enriched, key=lambda x: (_RANK.get(x[1], 1), _to_min(x[0].start_time))
    )
    ordered = [s for s, _ in ordered_pairs]
    priority_order = [
        PriorityOrderItem(
            title=s.title,
            priority=eff,
            reason=_schedule_reason(s.category),
        )
        for s, eff in ordered_pairs
    ]

    high_todos = [t for t in req.todos if not t.is_done and (
        t.priority == "high" or any(
            kw in t.title for kw in _priority_rules().get("high_keywords", []))
    )]

    # ----- summary (template) -----
    if schedules:
        listing = ", ".join(_summary_schedule_phrase(s) for s in schedules)
        last_phrase = _summary_schedule_phrase(schedules[-1])
        template_summary = s_tpl["has_schedules"].format(
            listing=listing, subject_particle=_i_ga(last_phrase)
        )
        top = ordered[0] if ordered else None
        if top is not None and (top.category or "").lower() in tip_cats:
            prep = (_todo_stem(high_todos[0].title) if high_todos
                    else brules.get("default_prep_word", "준비물"))
            template_summary += s_tpl["prep_tip"].format(
                top_title=top.title, prep=prep, object_particle=_eul_reul(prep)
            )
    else:
        template_summary = s_tpl["no_schedules"]

    # ----- summary (LLM, optional) -----
    llm_summary = None
    try:
        base_system = "너는 사용자의 하루를 따뜻하고 간결하게 정리하는 한국어 비서야. 2~3문장으로만 요약해."
        if preferences:
            from backend.services import assistant_style_service as style
            base_system = style.styled_system(base_system, preferences)
        llm_summary = llm_service.generate(
            _build_prompt(req, priority_order),
            system=base_system,
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
        key_points.append(k_tpl["top_schedule"].format(
            time_prefix=prefix, title=top.title, subject_particle=_i_ga(top.title)
        ))
    for t in high_todos:
        stem = _todo_stem(t.title)
        if t.title.endswith(checklist_suffix):
            key_points.append(k_tpl["todo_checklist"].format(
                stem=stem, object_particle=_eul_reul(stem)
            ))
        else:
            key_points.append(k_tpl["todo_reminder"].format(
                title=t.title, object_particle=_eul_reul(t.title)
            ))
    for s in ordered[1:]:
        dp = _daypart(s.start_time)
        prefix = f"{dp}{daypart_suffix}" if dp else ""
        key_points.append(k_tpl["other_schedule"].format(
            daypart_prefix=prefix, title=s.title, subject_particle=_i_ga(s.title)
        ))

    if isinstance(max_kp, int) and max_kp > 0:
        key_points = key_points[:max_kp]

    preferences = user_preference_service.get_user_preferences(None)
    if schedules:
        tts_text = tts_response_builder.build_tts_response(
            intent="briefing_today",
            slots={"count": len(schedules), "main_event": ordered[0].title if ordered else schedules[0].title},
            preferences=preferences,
        )
    else:
        tts_text = tts_response_builder.build_tts_response(
            intent="briefing_empty", slots={}, preferences=preferences,
        )

    return DailyBriefingData(
        summary=summary,
        key_points=key_points,
        priority_order=priority_order,
        tts_text=tts_text,
    )
