"""Rule-based Korean natural-language schedule parser.

Extracts intent, date/time expressions, title, category and priority from a
free-text utterance. Never raises on bad input: anything it cannot resolve is
reported via `missing_fields`.

Policy notes:
- Title strips date/time expressions, command verbs (잡아/추가해/등록해/저장해/
  넣어/해야 해 ...), deadline markers (~까지) and filler nouns (일정/스케줄) /
  leading fillers (할 일로/일정으로 ...). '예약'은 일정의 핵심 목적이므로 title 에
  보존한다 ("치과 예약" -> "치과 예약").
- To-do intent: strong to-do signals (작성/제출/정리/장보기/마감/까지 ...) classify
  as create_todo, unless a schedule-override keyword (예약/회의/약속/병원/알림 ...)
  is present.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from backend.core.config import settings
from backend.database.schema.personalization_schema import TONES
from backend.database.schema.schedule_schema import (
    ScheduleDraft,
    ScheduleParseData,
    ScheduleParseRequest,
    ScheduleSlots,
)
from backend.services.schedule_title_extractor import (
    TITLE_CONFIDENCE_THRESHOLD,
    extract_schedule_title,
)

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"

_WEEKDAY = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# Command/verb endings to strip from the end of a title (longest first).
# '~줘' 없는 명령형(잡아/추가해/등록해/저장해/넣어 등)도 함께 제거한다.
_VERB_TAILS = sorted(
    [
        "잡아줘", "잡아 줘", "추가해줘", "추가 해줘", "넣어줘", "넣어 줘",
        "알림해줘", "알림 해줘", "알려줘", "등록해줘", "만들어줘", "예약해줘",
        "저장해줘", "저장 해줘",
        # bare command forms (without 줘)
        "추가해", "추가 해", "등록해", "등록 해", "저장해", "저장 해",
        "예약해", "만들어", "알림해", "넣어", "잡아",
        "해야 해", "해야해", "해야 돼", "해야돼", "해야겠다", "해야지",
        "해줘", "해 줘", "있어", "줘", "좀", "해주세요", "주세요", "잡고",
    ],
    key=len,
    reverse=True,
)

# Filler nouns that are noise when trailing a title ("운동 일정" -> "운동").
# '예약'은 제거하지 않는다 — 일정의 핵심 목적이라 title 에 남긴다 ("치과 예약").
_NOISE_NOUNS = ["일정", "스케줄"]

# Combined trailing tokens stripped from a title, longest first.
_TITLE_TAILS = sorted(_VERB_TAILS + _NOISE_NOUNS, key=len, reverse=True)

# Filler tokens dropped when they LEAD a title:
#   "일정 회의" -> "회의", "할 일로 장보기" -> "장보기".
_LEADING_NOISE = ("할 일로", "할일로", "일정으로", "일정", "스케줄", "더", "동안")

# --- intent classification signals ----------------------------------------- #
# 강한 To-do 신호.
_TODO_KEYWORDS = (
    "해야 해", "해야돼", "해야 돼", "해야겠다", "해야지",
    "하기", "할 일", "할일", "장보기", "장 보기",
    "작성", "제출", "정리", "준비", "확인", "마감", "까지",
)
# 아래 신호가 있으면 To-do 신호가 있어도 일정(schedule)으로 유지한다.
# ('알림'은 시간 기반 리마인더 → 일정성으로 취급)
_SCHEDULE_OVERRIDE = (
    "예약", "회의", "미팅", "약속", "수업", "병원", "치과", "방문", "알림",
)

# category 기반 기본 title (title 이 비었을 때만 사용).
_CATEGORY_DEFAULT_TITLE = {
    "hospital": "병원 예약",
    "meeting": "회의",
    "beauty": "미용실 예약",
    "restaurant": "식당 예약",
    "school": "수업",
    "exercise": "운동",
    "shopping": "장보기",
}

_DURATION_RE = re.compile(
    r"(?:\d+\s*시간(?:\s*\d+\s*분)?|\d+\s*분)(?:\s*(?:짜리|동안|만)(?=\s|$))?"
)


@lru_cache(maxsize=1)
def _load_category_rules() -> Tuple[list, str]:
    with open(_RULES_DIR / "category_rules.json", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("rules", []), cfg.get("default", "etc")


@lru_cache(maxsize=1)
def _load_priority_rules() -> dict:
    with open(_RULES_DIR / "priority_rules.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_tone_rules() -> dict:
    with open(_RULES_DIR / "tts_tone_rules.json", encoding="utf-8") as f:
        return json.load(f).get("tones", {})


def _base_datetime(req: ScheduleParseRequest) -> datetime:
    if req.current_datetime:
        try:
            return datetime.fromisoformat(req.current_datetime)
        except ValueError:
            pass
    return datetime.now()


# --------------------------------------------------------------------------- #
# Date parsing
# --------------------------------------------------------------------------- #
def _extract_date(text: str, base: datetime) -> Tuple[Optional[str], Optional[str]]:
    """Return (resolved 'YYYY-MM-DD', matched expression) or (None, None)."""
    base_date = base.date()

    # ISO 'YYYY-MM-DD'
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return base_date.replace(year=y, month=mo, day=d).isoformat(), m.group(0)
            except ValueError:
                pass

    # 다음 주 <요일> / 이번 주 <요일>
    m = re.search(r"(다음\s*주|담주|이번\s*주|금주)\s*([월화수목금토일])요일", text)
    if m:
        target = _WEEKDAY[m.group(2)]
        delta = (target - base_date.weekday()) % 7
        this_week = base_date + timedelta(days=delta)
        if re.match(r"다음\s*주|담주", m.group(1)):
            this_week += timedelta(days=7)
        return this_week.isoformat(), m.group(0)

    # N월 N일
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = base_date.year
        try:
            resolved = base_date.replace(year=year, month=month, day=day)
        except ValueError:
            return None, m.group(0)
        if resolved < base_date:
            resolved = resolved.replace(year=year + 1)
        return resolved.isoformat(), m.group(0)

    # M/D (슬래시 표기, 예: '7/3', '7 / 3'). 월 1-12, 일 1-31 일 때만 날짜로 인정.
    m = re.search(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            year = base_date.year
            try:
                resolved = base_date.replace(year=year, month=month, day=day)
            except ValueError:
                resolved = None
            if resolved is not None:
                if resolved < base_date:
                    resolved = resolved.replace(year=year + 1)
                return resolved.isoformat(), m.group(0)

    # relative day words
    for word, offset in (("글피", 3), ("모레", 2), ("내일", 1), ("오늘", 0)):
        if word in text:
            return (base_date + timedelta(days=offset)).isoformat(), word

    # bare weekday (e.g. 금요일) -> next occurrence (including today)
    m = re.search(r"([월화수목금토일])요일", text)
    if m:
        target = _WEEKDAY[m.group(1)]
        delta = (target - base_date.weekday()) % 7
        return (base_date + timedelta(days=delta)).isoformat(), m.group(0)

    return None, None


# --------------------------------------------------------------------------- #
# Date-range parsing (기간 일정: 시작일 + 종료일)
# --------------------------------------------------------------------------- #
# 종료일 후보로 인정하는 날짜 토큰(ISO / N월 M일 / M/D / N일 단독).
_DATE_TOKEN = r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*/\s*\d{1,2}|\d{1,2}\s*일)"
# 범위 구분 기호(물결/대시 계열).
_RANGE_MARK = r"(?:~|∼|〜|–|—|-)"


def _resolve_end_expr(expr: str, base: datetime, start_date: str) -> Optional[str]:
    """종료일 표현 하나를 'YYYY-MM-DD' 로 해석. 'N일' 단독이면 시작일의
    연/월을 물려받는다. 실패 시 None."""
    expr = (expr or "").strip()
    # "9일" / "9" 처럼 일(day)만 있는 경우 → 시작일의 연·월 사용.
    m = re.fullmatch(r"(\d{1,2})\s*일?", expr)
    if m:
        try:
            y, mo = int(start_date[0:4]), int(start_date[5:7])
            day = int(m.group(1))
            return datetime(y, mo, day).date().isoformat()
        except ValueError:
            return None
    # 그 외에는 일반 날짜 파서를 재사용(상대표현/요일/월일/ISO 등 모두 지원).
    value, _ = _extract_date(expr, base)
    return value


def _extract_date_range(
    text: str, base: datetime, start_date: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """기간 일정의 (종료일 'YYYY-MM-DD', 매칭된 원문 표현)을 반환. 단일 일정이면
    (None, None). [start_date] 는 이미 해석된 시작일로, 일(day)만 있는 종료
    표현의 연·월을 물려받는 데 쓴다.

    지원: 'A부터 B까지', 'A~B', 'A-B'. 종료일이 시작일보다 뒤일 때만 인정한다.
    (마감 표현 'X까지' 단독은 '부터'가 없으므로 기간으로 보지 않는다.)
    """
    if not start_date:
        return None, None

    right: Optional[str] = None
    matched: Optional[str] = None

    m = re.search(r"(.+?)\s*부터\s*(.+?)\s*까지", text)
    if m:
        right = m.group(2)
        matched = m.group(0)
    else:
        m2 = re.search(rf"({_DATE_TOKEN})\s*{_RANGE_MARK}\s*({_DATE_TOKEN})", text)
        if m2:
            right = m2.group(2)
            matched = m2.group(0)

    if not right:
        return None, None

    end_date = _resolve_end_expr(right, base, start_date)
    if not end_date or end_date <= start_date:
        return None, None
    return end_date, matched


# --------------------------------------------------------------------------- #
# Time parsing
# --------------------------------------------------------------------------- #
def _extract_time(text: str) -> Tuple[Optional[str], Optional[str], bool]:
    """Return (resolved 'HH:mm', matched expression, ambiguous)."""
    # HH:mm (24h)
    m = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}", m.group(0), False

    m = re.search(
        r"(오전|오후|아침|저녁|밤|점심|낮|새벽)?\s*(\d{1,2})\s*시(?!간)\s*"
        r"(?:(\d{1,2})\s*분|반)?",
        text,
    )
    if not m:
        return None, None, False

    meridiem, hour_s, minute_s = m.group(1), m.group(2), m.group(3)
    hour = int(hour_s)
    # '3시 반' -> 30분
    if minute_s:
        minute = int(minute_s)
    elif "반" in m.group(0):
        minute = 30
    else:
        minute = 0

    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None, None, False

    ambiguous = False

    if meridiem in ("오전", "아침", "새벽"):
        if hour == 12:
            hour = 0
    elif meridiem in ("오후", "저녁", "점심", "낮"):
        if hour < 12:
            hour += 12
    elif meridiem == "밤":
        if hour < 12:
            hour += 12
        elif hour == 12:
            hour = 0
    else:
        if 1 <= hour <= 11:
            hour += 12
        ambiguous = True

    return f"{hour:02d}:{minute:02d}", m.group(0).strip(), ambiguous


def _add_one_hour(hhmm: str) -> str:
    t = datetime.strptime(hhmm, "%H:%M") + timedelta(hours=1)
    return t.strftime("%H:%M")


# --------------------------------------------------------------------------- #
# Title / category / priority
# --------------------------------------------------------------------------- #
def _extract_title(text: str, date_expr: Optional[str], time_expr: Optional[str]) -> str:
    work = text
    for expr in (date_expr, time_expr):
        if expr:
            work = work.replace(expr, " ")
    work = _DURATION_RE.sub(" ", work)
    # 마감 표현 제거 (금요일까지 / 저녁까지 / 3시까지 -> 토큰 통째로 제거)
    work = re.sub(r"\S*까지", " ", work)
    work = re.sub(r"(?:^|\s)에(?=\s|$)", " ", " " + work + " ")
    work = re.sub(r"\s+", " ", work).strip()

    changed = True
    while changed and work:
        changed = False
        for v in _TITLE_TAILS:
            if work.endswith(v):
                work = work[: -len(v)].strip()
                changed = True
                break
        if changed:
            continue
        for w in _LEADING_NOISE:
            if work == w or work.startswith(w + " "):
                work = work[len(w):].strip()
                changed = True
                break
    return work.strip()


# First-person / intent residue that the legacy cleaning above leaves behind
# ("나 병원 가려고" keeps 병원 but also 나/가려고). When such residue survives, we
# re-extract a concise title via the domain-aware title extractor. These markers
# appear in NONE of the locked title cases or the regression dataset, so this
# only ever changes the previously-broken path.
_TITLE_RESIDUE_MARKERS = (
    "나 ", "내가", "나는", "가려고", "하려고", "가야", "가기로", "하기로",
    "할 예정", "할 것 같", "가는 거", "먹는 ",
)


def _maybe_refine_title(title: str, text: str) -> str:
    """Replace a residue-laden title with a clean domain-based one when possible."""
    if not title:
        return title
    if not any(marker in f"{title} " for marker in _TITLE_RESIDUE_MARKERS):
        return title
    info = extract_schedule_title(text)
    if info["title"] and info["confidence"] >= TITLE_CONFIDENCE_THRESHOLD:
        return info["title"]
    return title


def _detect_category(*texts: str) -> str:
    rules, default = _load_category_rules()
    for text in texts:
        if not text:
            continue
        for rule in rules:
            for kw in rule["keywords"]:
                if kw in text:
                    return rule["category"]
    return default


def _detect_priority(category: str, *texts: str) -> str:
    cfg = _load_priority_rules()
    joined = " ".join(t for t in texts if t)
    if any(kw in joined for kw in cfg.get("high_keywords", [])):
        return "high"
    if any(kw in joined for kw in cfg.get("low_keywords", [])):
        return "low"
    cat_priority = cfg.get("category_priority", {})
    if category in cat_priority:
        return cat_priority[category]
    return cfg.get("default", "medium")


def _default_title(category: str, is_todo: bool) -> str:
    if is_todo:
        return "새 할 일"
    return _CATEGORY_DEFAULT_TITLE.get(category, "새 일정")


def _classify_intent(text: str, has_date: bool, has_time: bool,
                     has_title: bool, has_category: bool) -> str:
    """create_todo / create_schedule / unknown."""
    is_override = any(k in text for k in _SCHEDULE_OVERRIDE)
    is_todo_signal = (not is_override) and any(k in text for k in _TODO_KEYWORDS)
    if is_todo_signal:
        return "create_todo"
    if has_date or has_time or has_title or has_category:
        return "create_schedule"
    return "unknown"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def parse_schedule(req: ScheduleParseRequest) -> ScheduleParseData:
    text = (req.input or "").strip()
    base = _base_datetime(req)

    date_value, date_expr = _extract_date(text, base)
    # 기간 일정(시작일~종료일). 종료일이 있으면 제목 정제 시 범위 표현을 통째로
    # 제거해 "여행" 같은 순수 제목만 남긴다.
    end_date_value, range_expr = _extract_date_range(text, base, date_value)
    start_time, time_expr, ambiguous = _extract_time(text)
    end_time = _add_one_hour(start_time) if start_time else None
    if range_expr:
        title = _extract_title(text.replace(range_expr, " "), None, time_expr)
    else:
        title = _extract_title(text, date_expr, time_expr)
    title = _maybe_refine_title(title, text)

    category = _detect_category(title, re.sub(re.escape(time_expr or ""), "", text))
    priority = _detect_priority(category, title, text)

    missing: List[str] = []
    if not date_value:
        missing.append("date")
    if not start_time:
        missing.append("time")
    if not title:
        missing.append("title")
    if ambiguous:
        missing.append("time_ambiguity")

    has_date, has_time = bool(date_value), bool(start_time)
    has_title, has_category = bool(title), category != "etc"

    intent = _classify_intent(text, has_date, has_time, has_title, has_category)
    is_todo = intent == "create_todo"

    confidence = round(
        min(
            0.95,
            0.40
            + 0.18 * has_date
            + 0.18 * has_time
            + 0.10 * has_title
            + 0.08 * has_category,
        ),
        2,
    )

    final_title = title or _default_title(category, is_todo)

    slots = ScheduleSlots(
        title=title or None,
        date_expression=date_expr,
        time_expression=time_expr,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        category=category,
        location=None,
    )

    # 음성 입력(input_type="voice")이면 초안 source 를 "voice" 로 표시한다.
    # InputType 은 str Enum 이라 "voice" 문자열 비교로 충분하다.
    source = "voice" if req.input_type == "voice" else "ai"

    # 기간 일정 종료일은 DB 스키마 불변을 위해 memo 의 `end_date:` 규칙으로 저장한다
    # (기존 캘린더가 이미 인식하는 방식). 파싱 응답 계약(slots/draft 키)도 그대로 유지.
    draft = ScheduleDraft(
        title=final_title,
        category=category,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        location=None,
        memo=(f"end_date: {end_date_value}" if end_date_value else None),
        priority=priority,
        source=source,
    )

    tts_text = _build_tts_text(
        intent=intent,
        missing=missing,
        title=final_title,
        date_value=date_value,
        start_time=start_time,
    )
    tts_text = _apply_tone_style(tts_text, req.tone)
    # AI voice-style override (only when the caller sent assistant-style prefs;
    # otherwise tts_text stays byte-identical to the legacy output -> locked tests safe).
    tts_text = _maybe_apply_assistant_style(
        req, tts_text, intent=intent, missing=missing, title=final_title,
        date_value=date_value, start_time=start_time, is_todo=is_todo,
    )

    return ScheduleParseData(
        intent=intent,
        confidence=confidence,
        slots=slots,
        schedule_draft=draft,
        missing_fields=missing,
        tts_text=tts_text,
    )


import logging as _logging

_style_log = _logging.getLogger("assistant_style")

# canonical (assistant_style_service) -> tts_response_builder vocabulary
_BUILDER_TONE = {"formal": "polite", "friendly": "friendly", "caring": "caring", "concise": "concise"}
_BUILDER_LENGTH = {"short": "short", "medium": "normal", "long": "detailed"}


def _maybe_apply_assistant_style(
    req: ScheduleParseRequest,
    tts_text: str,
    *,
    intent: str,
    missing: List[str],
    title: str,
    date_value: Optional[str],
    start_time: Optional[str],
    is_todo: bool,
) -> str:
    """Regenerate tts_text in the user's persona style — ONLY when the request
    carries assistant-style prefs. No prefs -> returns the input unchanged so the
    legacy /ai/schedule/parse contract (and its locked tests) is untouched."""
    prefs = {
        "assistant_tone": getattr(req, "assistant_tone", None),
        "response_length": getattr(req, "response_length", None),
        "reminder_strength": getattr(req, "reminder_strength", None),
    }
    if not any(prefs.values()):
        return tts_text
    try:
        from backend.services import assistant_style_service as style
        from backend.services import tts_response_builder

        profile = style.build_style_profile(prefs)
        _style_log.info("[STYLE DEBUG] parse_schedule preferences=%s", prefs)
        _style_log.info("[STYLE DEBUG] profile=%s", profile)
        _style_log.info("[STYLE DEBUG] before_tts=%s", tts_text)

        success = bool(date_value and start_time and title) and intent != "unknown"
        if success:
            builder_prefs = {
                "assistant_tone": _BUILDER_TONE.get(profile["tone"], "friendly"),
                "response_length": _BUILDER_LENGTH.get(profile["length"], "normal"),
                "nudge_strength": style.STRENGTH_TO_NUDGE.get(profile["strength"], "medium"),
            }
            intent_key = "todo_create_success" if is_todo else "schedule_create_success"
            styled = tts_response_builder.build_tts_response(
                intent=intent_key,
                slots={"title": title, "date": date_value, "time": start_time},
                preferences=builder_prefs,
            )
        else:
            norm_missing = [m for m in ("title", "date", "time") if m in missing]
            clar_title = None if "title" in missing else title
            styled = style.build_clarification_text(
                clar_title, norm_missing or ["date", "time"], profile
            )
        _style_log.info("[STYLE DEBUG] after_tts=%s", styled)
        return styled or tts_text
    except Exception as exc:  # never break parsing over a styling error
        _style_log.warning("[STYLE DEBUG] style application failed: %s", exc)
        return tts_text


def _build_tts_text(
    *,
    intent: str,
    missing: List[str],
    title: str,
    date_value: Optional[str],
    start_time: Optional[str],
) -> str:
    """음성 안내(TTS)용 문장을 상태에 따라 생성한다.

    - 실패(intent=unknown): 다시 말하기 유도
    - 부분 인식(날짜/시간 누락): 보완 요청
    - 성공: 요약 + 등록 확인
    """
    if intent == "unknown":
        return "일정 정보를 정확히 듣지 못했어요. 날짜와 시간을 포함해서 다시 말해주세요."
    if "date" in missing or "time" in missing:
        return "일정 정보를 일부만 이해했어요. 날짜나 시간을 다시 확인해주세요."
    return f"{title} 일정을 {date_value} {start_time}으로 정리했어요. 등록할까요?"


def _apply_tone_style(text: str, tone: Optional[str]) -> str:
    """Rule-based tone post-process on an already-built tts_text.

    'neutral' (or missing/invalid tone) applies zero rules, so tts_text stays
    byte-identical to the original un-styled sentence.
    """
    if not tone or tone == "neutral" or tone not in TONES:
        return text
    for rule in _load_tone_rules().get(tone, []):
        text = text.replace(rule["find"], rule["replace"])
    return text


# --------------------------------------------------------------------------- #
# LLM fallback (stub) — enabled later without touching callers
# --------------------------------------------------------------------------- #
def parse_schedule_with_llm_fallback(
    request_text: str,
    *,
    current_datetime: Optional[str] = None,
    timezone: str = "Asia/Seoul",
) -> Optional[dict]:
    """LLM fallback for hard/complex utterances. STUB — returns None for now.

    Intended trigger conditions (decided by the caller):
      * rule-based title confidence < ``TITLE_CONFIDENCE_THRESHOLD``
      * rule-based title is None (unclear)
      * long / compound sentence likely to hold multiple schedules

    Gated by ``settings.ENABLE_LLM_SCHEDULE_PARSE`` (default False) so the parser
    works fully offline today. When enabled, wire an OpenAI JSON-mode call here
    (see ``backend.services.llm_service.generate`` and the JSON-first prompt in
    ``schedule_llm_parser``) and return a dict shaped like ``build_schedule_plan``
    so the caller can merge/replace fields transparently.

    Prompt template (fill {today}/{timezone}/{text}); model MUST return JSON only::

        You are a schedule parser for a Korean AI secretary.
        Base date: {today}   Timezone: {timezone}
        Rules:
          1. Convert relative dates (오늘/내일/이번 주 금요일 ...) to YYYY-MM-DD.
          2. Convert times (오후 3시/저녁 7시/3시 반) to HH:MM (24h).
          3. Unknown field -> null. NEVER invent a date/time/location.
          4. confidence in [0, 1].
        Return ONLY this JSON object:
          {
            "title":       string | null,
            "category":    "health"|"personal"|"meeting"|"study"|"exercise"|"meal"|"other",
            "date":        "YYYY-MM-DD" | null,
            "start_time":  "HH:MM" | null,
            "end_time":    "HH:MM" | null,
            "confidence":  number
          }
        User input: {text}
    """
    if not settings.ENABLE_LLM_SCHEDULE_PARSE:
        return None
    # TODO: call llm_service.generate(...) with the prompt above, parse JSON,
    # validate (no fabricated date/time), and return the normalized dict.
    return None


# --------------------------------------------------------------------------- #
# High-level orchestration (title + slots + clarification, additive)
# --------------------------------------------------------------------------- #
def build_schedule_plan(
    request_text: str,
    current_datetime: Optional[str] = None,
    preferences: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Orchestrate the improved pipeline into a flat, clarification-aware dict.

    Pipeline: rule-based title extraction -> (optional) LLM fallback -> date/time
    slot extraction (never fabricated) -> missing-field detection -> clarification
    message. This is ADDITIVE and does not alter the locked ``parse_schedule``
    response consumed by the Flutter frontend.

    Voice/persona style: pass `preferences` (assistant_tone/response_length/
    reminder_strength) directly, or a `user_id` to look them up. When neither is
    given the clarification wording is the default rule-base (unchanged).
    """
    # Local imports avoid an import cycle (slot extractor imports this module).
    from backend.services import schedule_clarification, schedule_rule_loader
    from backend.services import schedule_slot_extractor

    if preferences is None and user_id:
        try:
            from backend.services import user_preference_service
            preferences = user_preference_service.get_user_preferences(user_id)
        except Exception:
            preferences = None

    text = (request_text or "").strip()
    title_info = extract_schedule_title(text)
    slots = schedule_slot_extractor.extract_schedule_slots(text, current_datetime)

    # LLM fallback hook (stub returns None unless ENABLE_LLM_SCHEDULE_PARSE).
    if (
        title_info["title"] is None
        or title_info["confidence"] < TITLE_CONFIDENCE_THRESHOLD
    ):
        llm = parse_schedule_with_llm_fallback(
            text, current_datetime=current_datetime
        )
        if llm and llm.get("title"):
            title_info = {
                "title": llm["title"],
                "category": llm.get("category", title_info["category"]),
                "confidence": float(llm.get("confidence", 0.7)),
                "source": "llm_fallback",
                "matched_keyword": None,
                "participants": title_info.get("participants", []),
            }

    category = title_info["category"]
    title = title_info["title"]
    title_confident = bool(title) and title_info["confidence"] >= TITLE_CONFIDENCE_THRESHOLD

    missing: List[str] = []
    if not title_confident:
        title = None
        missing.append("title")
    # date/time — never fabricated; taken straight from the slot extractor.
    missing.extend(slots["missing_fields"])
    # location — category-dependent policy; never fabricated.
    location = slots["location"]
    if _needs_location(schedule_rule_loader, category, text, location):
        missing.append("location")

    date_text = slots["date_expression"] or slots["date"]
    time_text = slots["time_expression"] or slots["time"]
    clar = schedule_clarification.build_clarification(
        category=category,
        title=title,
        missing_fields=missing,
        preferences=preferences,
        date_text=date_text,
        time_text=time_text,
    )

    confidence = title_info["confidence"] if title_confident else min(
        title_info["confidence"], 0.4
    )
    confidence = round(
        min(0.98, confidence + 0.03 * bool(slots["date"]) + 0.03 * bool(slots["start_time"])),
        2,
    )

    return {
        "title": title,
        "category": category,
        "confidence": confidence,
        "title_source": title_info["source"],
        "matched_keyword": title_info["matched_keyword"],
        "participants": title_info.get("participants", []),
        "date": slots["date"],
        "time": slots["time"],
        "start_time": slots["start_time"],
        "end_time": slots["end_time"],
        "ambiguous": slots["ambiguous"],
        "location": location,
        "missing_fields": missing,
        "status": clar["status"],
        "clarification_message": clar["clarification_message"],
        "tts_text": clar["tts_text"],
    }


def _needs_location(rule_loader, category: str, text: str, location) -> bool:
    """Category-driven location requirement (see schedule_location_policy.json).

    Order: already-extracted -> no; online keyword -> no; required category ->
    yes; optional category with a place keyword -> yes; otherwise -> no.
    """
    if location:
        return False
    policy = rule_loader.load_location_policy()
    if any(k in text for k in policy.get("online_keywords", [])):
        return False
    if category in policy.get("location_required_categories", []):
        return True
    if category in policy.get("location_optional_categories", []):
        return any(k in text for k in policy.get("place_required_keywords", []))
    return False
