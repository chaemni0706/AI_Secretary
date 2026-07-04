"""Enhanced schedule parse orchestrator + confirm save.

Pipeline for POST /ai/schedule/parse/enhanced:

    natural language
      -> resolve base date in the requested timezone (zoneinfo)
      -> rule-based parse (always; the safety net)
      -> LLM parse (optional; JSON-first + few-shot)
      -> validate the LLM result against a list of failure conditions
      -> merge (hybrid): rule wins date/time, LLM wins title/category
      -> flat EnhancedParseData + warnings + parse_source + clarification hints

`confirm_schedule` persists a user-approved parse via the existing local
schedule service (reusing `to_schedule_create_request`).

Design goal: NEVER return a 500. Missing/uncertain info is surfaced in
`warnings`; on any unexpected error the parse degrades to the rule-based result,
and confirm raises ValueError (router -> 422) instead of crashing.
"""

from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import datetime
from datetime import time as dtime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.local_schedule_schema import (
    ScheduleCreate,
    ScheduleDraftInput,
    ScheduleRead,
)
from backend.database.schema.todo_schema import TodoCreate, TodoRead
from backend.database.schema.schedule_parse_schema import (
    EnhancedParseData,
    EnhancedParseRequest,
    ScheduleConfirmRequest,
)
from backend.services import local_schedule_service as sched_service
from backend.services import todo_service
from backend.services import schedule_llm_parser as llm_parser
from backend.services import schedule_rule_parser as rule_parser

_DEFAULT_TZ = "Asia/Seoul"
_MAX_TEXT_LEN = 500          # inputs longer than this are truncated for parsing
_LOW_CONFIDENCE = 0.3        # below this, the LLM result is discarded
_MAX_EXTRA_KEYS = 3          # more hallucinated keys than this -> discard LLM
_LLM_TITLE_MIN_CONF = 0.5    # LLM title/category only trusted at/above this
_MAX_TITLE_LEN = 60

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# trailing Korean particles stripped when comparing a location to the source text
_LOC_PARTICLES = ("에서는", "에서의", "에서", "에는", "에게", "까지", "부터", "으로", "로", "에", "의", "은", "는", "이", "가")
# representative place suffixes: if the whole location isn't found, try its stem
_LOC_SUFFIXES = ("스터디룸", "도서관", "병원", "카페", "식당", "회사", "학교", "센터", "역", "점")


# --------------------------------------------------------------------------- #
# item type (EVENT vs TODO) — documented, keyword-based, MVP policy
# --------------------------------------------------------------------------- #
# NOTE (Flutter contract / MVP limitation): item_type detection is purely
# keyword based. An EVENT signal always wins over a TODO signal, and an
# ambiguous sentence with no signal defaults to "EVENT". These lists are the
# documented contract (see docs/flutter_parse_save_dashboard_contract.md);
# they are intentionally kept independent of the legacy /ai/schedule/parse
# intent classifier so tightening them here can't regress that locked endpoint.
_EVENT_SIGNALS = ("예약", "회의", "약속", "미팅", "방문", "진료", "병원", "치과", "수업", "알림")
_TODO_SIGNALS = (
    "해야 해", "해야해", "해야돼", "해야 돼", "해야 함", "해야함",
    "제출", "완료", "마감", "까지", "할 일", "할일", "작성", "정리", "준비",
)


def _detect_item_type(text: str) -> str:
    """Return 'TODO' for a to-do signal without an EVENT override, else 'EVENT'.
    Ambiguous input (no signal) defaults to 'EVENT' (MVP policy)."""
    if any(k in text for k in _EVENT_SIGNALS):
        return "EVENT"
    if any(k in text for k in _TODO_SIGNALS):
        return "TODO"
    return "EVENT"


_MSG_OK = "일정 정보를 파싱했습니다."
_MSG_PARTIAL = "일부 정보가 부족하지만 일정 정보를 생성했습니다."


def _valid_date(value) -> bool:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        date_cls.fromisoformat(value)
        return True
    except ValueError:
        return False


def _norm_time(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    m = _TIME_RE.match(value.strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


# --------------------------------------------------------------------------- #
# timezone / base date
# --------------------------------------------------------------------------- #
def _resolve_base(today: Optional[str], tz_name: Optional[str]) -> Tuple[datetime, str, List[str]]:
    """Return (naive base datetime at 00:00, applied timezone, warnings).

    - `today` (valid 'YYYY-MM-DD') wins for deterministic tests/debugging.
    - Otherwise the current date IN the requested timezone is used.
    - An invalid timezone falls back to Asia/Seoul with a warning.
    """
    warnings: List[str] = []
    requested = (tz_name or _DEFAULT_TZ).strip() or _DEFAULT_TZ
    applied, tz = requested, None
    try:
        tz = ZoneInfo(requested)
    except Exception:
        warnings.append(f"유효하지 않은 시간대 '{requested}'라 {_DEFAULT_TZ}로 대체했습니다.")
        applied = _DEFAULT_TZ
        try:
            tz = ZoneInfo(_DEFAULT_TZ)
        except Exception:
            tz = None

    if today:
        try:
            d = date_cls.fromisoformat(today)
            return datetime.combine(d, dtime(0, 0)), applied, warnings
        except (ValueError, TypeError):
            warnings.append("today 형식이 올바르지 않아 무시했습니다.")

    now = datetime.now(tz) if tz is not None else datetime.now()
    return datetime.combine(now.date(), dtime(0, 0)), applied, warnings


# --------------------------------------------------------------------------- #
# location grounding
# --------------------------------------------------------------------------- #
def _strip_particles(token: str) -> str:
    for p in _LOC_PARTICLES:
        if token.endswith(p) and len(token) > len(p):
            return token[: -len(p)]
    return token


def _location_supported(loc: str, text: str) -> bool:
    """True if `loc` is grounded in `text`, tolerant of spacing, trailing
    particles (강남역에서 -> 강남역) and representative place suffixes."""
    if not loc or not loc.strip():
        return False
    text_ns = re.sub(r"\s+", "", text)
    cand = _strip_particles(loc.strip())
    cand_ns = re.sub(r"\s+", "", cand)
    if not cand_ns:
        return False
    if cand_ns in text_ns:
        return True
    # try dropping a representative suffix and matching the stem (강남역 -> 강남)
    for suf in _LOC_SUFFIXES:
        if cand_ns.endswith(suf) and len(cand_ns) > len(suf):
            stem = cand_ns[: -len(suf)]
            if stem and stem in text_ns:
                return True
    return False


# --------------------------------------------------------------------------- #
# LLM result validation
# --------------------------------------------------------------------------- #
def _validate_llm(
    raw: Optional[dict], today: date_cls, text: str
) -> Tuple[Optional[Dict], List[str]]:
    """Keep only valid fields from a raw LLM dict. Returns (cleaned, warnings)."""
    if not isinstance(raw, dict):
        return None, []

    warnings: List[str] = []
    cleaned: Dict = {}

    title = raw.get("title")
    if isinstance(title, str) and title.strip() and len(title.strip()) <= _MAX_TITLE_LEN:
        cleaned["title"] = title.strip()

    d = raw.get("date")
    if _valid_date(d):
        if date_cls.fromisoformat(d) < today:
            warnings.append("과거 날짜로 해석되어 날짜 정보를 제외했습니다.")
        else:
            cleaned["date"] = d
    elif isinstance(d, str) and d.strip():
        warnings.append("LLM 날짜 형식이 올바르지 않아 제외했습니다.")

    st = _norm_time(raw.get("start_time"))
    if st:
        cleaned["start_time"] = st
    et = _norm_time(raw.get("end_time"))
    if et:
        cleaned["end_time"] = et

    cat = raw.get("category")
    if isinstance(cat, str) and cat in rule_parser.allowed_categories():
        cleaned["category"] = cat

    # anti-hallucination: accept a location only if it is grounded in the text
    loc = raw.get("location")
    if isinstance(loc, str) and loc.strip():
        if _location_supported(loc, text):
            cleaned["location"] = loc.strip()
        else:
            warnings.append("장소 정보의 근거를 원문에서 찾지 못해 제외했습니다.")

    memo = raw.get("memo")
    if isinstance(memo, str) and memo.strip():
        cleaned["memo"] = memo.strip()

    cleaned["is_all_day"] = raw.get("is_all_day") is True

    conf = raw.get("confidence")
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.5
    cleaned["confidence"] = max(0.0, min(1.0, conf))

    schema_keys = {
        "title", "date", "start_time", "end_time", "category",
        "location", "memo", "is_all_day", "confidence",
    }
    cleaned["_extra"] = sum(1 for k in raw if k not in schema_keys)

    return cleaned, warnings


def _llm_usable(clean: Optional[Dict]) -> bool:
    if not clean:
        return False
    has_core = bool(clean.get("title") or clean.get("date") or clean.get("start_time"))
    return (
        has_core
        and clean.get("confidence", 0.0) >= _LOW_CONFIDENCE
        and clean.get("_extra", 0) <= _MAX_EXTRA_KEYS
    )


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _confidence(
    *, date_val, start_time, title, category, rule_conf: float,
    llm_conf: float, usable: bool, agree: bool, conflict: bool, warnings_count: int,
) -> float:
    """Composite confidence (see spec §4). More filled fields raise it; warnings
    and LLM/rule conflicts lower it; date+time both missing keeps it modest."""
    score = 0.0
    if date_val:
        score += 0.20
    if start_time:
        score += 0.20
    if title:
        score += 0.15
    if category and category != "other":
        score += 0.15
    if usable:
        score += 0.15 * llm_conf
    score += 0.10 * rule_conf
    if agree:
        score += 0.05
    if conflict:
        score -= 0.15
    score -= 0.05 * warnings_count
    return round(max(0.0, min(1.0, score)), 2)


def _clarification(date_val, start_time, title, is_all_day) -> Tuple[List[str], List[str]]:
    """Return (missing_fields, clarification_questions)."""
    missing: List[str] = []
    questions: List[str] = []
    if not date_val:
        missing.append("date")
        questions.append("언제 일정으로 등록할까요?")
    if not start_time and not is_all_day:
        missing.append("start_time")
        questions.append("몇 시에 시작하는 일정인가요?")
    if not title:
        missing.append("title")
        questions.append("일정 제목을 무엇으로 할까요?")
    return missing, questions


def parse_enhanced(req: EnhancedParseRequest) -> Tuple[EnhancedParseData, str]:
    """Run the full LLM-first + fallback + hybrid pipeline. Never raises."""
    original = req.text or ""
    try:
        return _parse_enhanced_inner(req, original)
    except Exception:  # last-resort safety net: never 500
        data = EnhancedParseData(
            original_text=original, title="새 일정", category="other",
            confidence=0.3, parse_source="rule_fallback", timezone=_DEFAULT_TZ,
            warnings=["입력을 해석하는 중 문제가 발생하여 기본값으로 처리했습니다."],
            needs_clarification=True, missing_fields=["date", "start_time"],
            clarification_questions=["언제 일정으로 등록할까요?", "몇 시에 시작하는 일정인가요?"],
        )
        return data, _MSG_PARTIAL


def _parse_enhanced_inner(
    req: EnhancedParseRequest, original: str
) -> Tuple[EnhancedParseData, str]:
    base, applied_tz, warnings = _resolve_base(req.today, req.timezone)
    today = base.date()

    text = original.strip()
    if len(text) > _MAX_TEXT_LEN:
        text = text[:_MAX_TEXT_LEN]
        warnings.append("입력이 너무 길어 일부만 처리했습니다.")

    # 1) rule-based parse (always available)
    rule = rule_parser.parse(text, base)

    # 2) LLM parse (optional) + validation
    llm_clean: Optional[Dict] = None
    if req.use_llm:
        raw = llm_parser.parse(text, today=today.isoformat(), timezone=applied_tz)
        llm_clean, llm_warnings = _validate_llm(raw, today, text)
        if _llm_usable(llm_clean):
            warnings.extend(llm_warnings)
        else:
            llm_clean = None
    usable = llm_clean is not None

    # 3) hybrid merge -------------------------------------------------------- #
    date_val = rule["date"] or (llm_clean.get("date") if usable else None)
    date_src = "rule" if rule["date"] else ("llm" if date_val else None)

    start_time = rule["start_time"] or (llm_clean.get("start_time") if usable else None)
    time_src = "rule" if rule["start_time"] else ("llm" if start_time else None)

    if rule["start_time"]:
        end_time = rule["end_time"]
    elif usable and start_time:
        end_time = llm_clean.get("end_time")
    else:
        end_time = None

    if usable and llm_clean.get("title") and llm_clean.get("confidence", 0) >= _LLM_TITLE_MIN_CONF:
        title, title_src = llm_clean["title"], "llm"
    else:
        title, title_src = rule["title"], "rule"

    if usable and llm_clean.get("category") and llm_clean["category"] != "other":
        category, cat_src = llm_clean["category"], "llm"
    else:
        category, cat_src = rule["category"], "rule"

    if usable and llm_clean.get("location"):
        location, loc_src = llm_clean["location"], "llm"
    else:
        location, loc_src = rule["location"], ("rule" if rule["location"] else None)

    memo = llm_clean.get("memo") if usable else None
    memo_src = "llm" if memo else None

    is_all_day = bool(llm_clean.get("is_all_day")) if usable else False
    if start_time:
        is_all_day = False

    # LLM/rule agreement vs conflict on date/time
    ld, lt = (llm_clean.get("date"), llm_clean.get("start_time")) if usable else (None, None)
    conflict = usable and (
        (bool(ld) and bool(rule["date"]) and ld != rule["date"])
        or (bool(lt) and bool(rule["start_time"]) and lt != rule["start_time"])
    )
    agree = usable and not conflict and (
        (bool(ld) and ld == rule["date"]) or (bool(lt) and lt == rule["start_time"])
    )
    if conflict:
        warnings.append("LLM과 규칙 파서의 날짜/시간이 달라 규칙 결과를 사용했습니다.")

    # 4) parse_source
    srcs = {s for s in (date_src, time_src, title_src, cat_src, loc_src, memo_src) if s}
    if not usable:
        parse_source = "rule_fallback"
    elif "llm" in srcs and "rule" in srcs:
        parse_source = "hybrid"
    elif "llm" in srcs:
        parse_source = "llm"
    else:
        parse_source = "rule_fallback"

    # 5) warnings (missing info, ambiguity, past date)
    if date_val is None:
        warnings.append("날짜 정보가 필요합니다.")
    if start_time is None and not is_all_day:
        warnings.append("시간 정보가 필요합니다.")
    if rule.get("ambiguous") and start_time and time_src == "rule":
        warnings.append("오전/오후가 불명확하여 오후로 해석했습니다.")
    if date_val and _valid_date(date_val) and date_cls.fromisoformat(date_val) < today:
        warnings.append("과거 날짜로 보입니다. 날짜를 확인해주세요.")
    warnings = _dedupe(warnings)

    # 6) confidence (after warnings are finalized so the penalty applies)
    confidence = _confidence(
        date_val=date_val, start_time=start_time, title=title, category=category,
        rule_conf=rule["confidence"], llm_conf=(llm_clean or {}).get("confidence", 0.0),
        usable=usable, agree=agree, conflict=conflict, warnings_count=len(warnings),
    )

    # 7) clarification UX
    missing_fields, questions = _clarification(date_val, start_time, title, is_all_day)

    data = EnhancedParseData(
        original_text=original,
        title=title,
        date=date_val,
        start_time=start_time,
        end_time=end_time,
        category=category,
        location=location,
        memo=memo,
        is_all_day=is_all_day,
        confidence=confidence,
        parse_source=parse_source,
        item_type=_detect_item_type(text),
        timezone=applied_tz,
        base_date=today.isoformat(),
        warnings=warnings,
        needs_clarification=bool(missing_fields),
        clarification_questions=questions,
        missing_fields=missing_fields,
    )

    incomplete = date_val is None or (start_time is None and not is_all_day)
    return data, (_MSG_PARTIAL if incomplete else _MSG_OK)


def to_schedule_create_request(data: EnhancedParseData) -> ScheduleCreate:
    """Convert a parsed result into a ScheduleCreate for the local schedule API.

    Raises ValueError when required fields (date + start_time) are missing, so
    callers can decide whether to ask the user for more info before saving.
    """
    if not data.date or not data.start_time:
        raise ValueError("일정 저장에는 날짜와 시작 시간이 필요합니다.")
    return ScheduleCreate(
        title=data.title or "새 일정",
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        category=data.category,
        priority="medium",
        location=data.location,
        memo=data.memo,
        source="ai",
    )


# --------------------------------------------------------------------------- #
# Confirm: persist a user-approved parse into the local schedule store
# --------------------------------------------------------------------------- #
def confirm_schedule(db: Session, req: ScheduleConfirmRequest) -> ScheduleRead:
    """Save a confirmed parse. Raises ValueError (router -> 422) when the parsed
    result is too incomplete/invalid to store. Reuses the existing local schedule
    service; all-day events (no start_time) go through the from-draft path."""
    if not req.user_id or not req.user_id.strip():
        raise ValueError("user_id가 필요합니다.")

    p = req.parsed
    if not p.title or not p.title.strip():
        raise ValueError("일정 제목(title)이 필요합니다.")
    if not p.date or not _valid_date(p.date):
        raise ValueError("올바른 날짜(date, 'YYYY-MM-DD')가 필요합니다.")

    st = _norm_time(p.start_time) if p.start_time else None
    if p.start_time and st is None:
        raise ValueError("시작 시간(start_time) 형식이 올바르지 않습니다 (HH:MM).")
    et = _norm_time(p.end_time) if p.end_time else None
    if p.end_time and et is None:
        raise ValueError("종료 시간(end_time) 형식이 올바르지 않습니다 (HH:MM).")
    if not p.is_all_day and not st:
        raise ValueError("종일 일정이 아니라면 시작 시간(start_time)이 필요합니다.")

    user_id, calendar_id = repo.ensure_default_owner(db)

    if p.is_all_day and not st:
        draft = ScheduleDraftInput(
            title=p.title, category=p.category, date=p.date,
            start_time=None, end_time=et, location=p.location, memo=p.memo,
            priority="medium", source="ai",
        )
        return sched_service.create_schedule_from_draft(
            db, draft, user_id=user_id, calendar_id=calendar_id
        )

    parsed_data = EnhancedParseData(
        original_text=p.original_text or "", title=p.title, date=p.date,
        start_time=st, end_time=et, category=p.category, location=p.location,
        memo=p.memo, is_all_day=p.is_all_day,
    )
    sc = to_schedule_create_request(parsed_data)
    return sched_service.create_schedule(db, sc, user_id=user_id, calendar_id=calendar_id)


# --------------------------------------------------------------------------- #
# Todo conversion + confirm
# --------------------------------------------------------------------------- #
def to_todo_create_request(parsed) -> TodoCreate:
    """Convert a parsed result (EnhancedParseData or ConfirmParsedInput) into a
    TodoCreate. `date` maps to `due_date`. Raises ValueError when title/date are
    missing so the router can return 422 instead of persisting junk."""
    title = getattr(parsed, "title", None)
    date = getattr(parsed, "date", None)
    if not title or not str(title).strip():
        raise ValueError("할 일 제목(title)이 필요합니다.")
    if not date or not _valid_date(date):
        raise ValueError("올바른 마감일(due_date, 'YYYY-MM-DD')이 필요합니다.")
    return TodoCreate(
        title=str(title).strip(),
        due_date=date,
        priority="medium",
        completed=False,
        category=getattr(parsed, "category", None),
        memo=getattr(parsed, "memo", None) or getattr(parsed, "original_text", None),
        source="ai",
    )


def resolve_item_type(req: ScheduleConfirmRequest) -> str:
    """Resolve the item type to save as. Top-level item_type wins, then
    parsed.item_type, else defaults to EVENT. An explicitly provided value that
    is neither EVENT nor TODO raises ValueError (router -> 422)."""
    for candidate in (req.item_type, req.parsed.item_type):
        if candidate is None:
            continue
        val = str(candidate).strip().upper()
        if val in ("EVENT", "TODO"):
            return val
        raise ValueError(f"item_type은 'EVENT' 또는 'TODO'여야 합니다: '{candidate}'")
    return "EVENT"


def confirm_todo(db: Session, req: ScheduleConfirmRequest) -> TodoRead:
    """Save a confirmed to-do parse via the existing todo service. Raises
    ValueError (router -> 422) when the parsed result is too incomplete."""
    if not req.user_id or not req.user_id.strip():
        raise ValueError("user_id가 필요합니다.")
    payload = to_todo_create_request(req.parsed)
    user_id, _ = repo.ensure_default_owner(db)
    return todo_service.create_todo(db, payload, user_id=user_id)
