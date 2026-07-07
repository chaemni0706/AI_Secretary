"""Voice route orchestrator — dispatches a classified voice utterance to the
EXISTING feature service for its intent and shapes a uniform
``{intent, tts_text, screen_action, data, context}`` response.

No existing endpoint/service is modified in its public contract here; this
module only calls them. See ``voice_intent_router.py`` for classification and
``backend/api/voice.py`` for the HTTP entry point (``POST /voice/route``).

Never raises: any handler failure degrades to a safe fallback_chat response so
a voice turn never surfaces a 500.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database import repository as repo
from backend.database.schema.briefing_schema import (
    BriefingSchedule,
    BriefingTodo,
    DailyBriefingRequest,
)
from backend.database.schema.chat_schema import (
    ChatRespondRequest,
    ScheduleContext,
    ScheduleEvent,
    UserProfile,
)
from backend.core.config import settings
from backend.database.schema.local_schedule_schema import (
    ScheduleDraftInput,
    ScheduleRead,
    ScheduleUpdate,
)
from backend.database.schema.schedule_parse_schema import EnhancedParseRequest
from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.database.schema.voice_route_schema import (
    ScreenAction,
    VoiceRouteData,
    VoiceRouteRequest,
)
from backend.services import (
    briefing_generator,
    chat_orchestrator,
    local_schedule_service,
    memory_service,
    notification_plan_builder,
    place_recommendation_service,
    schedule_clarification,
    todo_service,
    voice_intent_router,
)
from backend.services import llm_service
from backend.services.naver_place_client import NaverApiError, NaverConfigError
from backend.services.schedule_parse_service import parse_enhanced
from backend.services.schedule_parser import parse_schedule

_logger = logging.getLogger("voice_route")

_DEFAULT_REMINDER_MINUTES = 30


# --------------------------------------------------------------------------- #
# small shared helpers
# --------------------------------------------------------------------------- #
def _today(req: VoiceRouteRequest) -> str:
    if req.current_datetime:
        try:
            return datetime.fromisoformat(req.current_datetime).date().isoformat()
        except ValueError:
            pass
    return datetime.now().date().isoformat()


def _todays_schedules(db: Session, user_id: str, date_str: str) -> List[ScheduleRead]:
    items = local_schedule_service.list_schedules(db, user_id=user_id)
    return [s for s in items if s.date == date_str and (s.status or "").upper() != "CANCELLED"]


def _naive_now_iso(req: VoiceRouteRequest) -> str:
    """Naive (no tzinfo) 'now' ISO string, matching the naive event start_time/
    end_time strings built for ScheduleContext below. Flutter sends
    current_datetime WITH an offset (e.g. '+09:00'); solution_recommender's
    datetime comparisons raise TypeError when comparing an offset-aware `now`
    against the naive event times, which chat_orchestrator's broad except
    silently swallows into a bland fallback answer. Stripping tzinfo here
    keeps both sides naive and avoids that silent degrade."""
    if req.current_datetime:
        try:
            return datetime.fromisoformat(req.current_datetime).replace(tzinfo=None).isoformat()
        except ValueError:
            pass
    return datetime.now().isoformat()


def _schedule_summary_sentence(todays: List[ScheduleRead]) -> str:
    if not todays:
        return "오늘은 등록된 일정이 없어요."
    listing = ", ".join(
        f"{(s.start_time + ' ') if s.start_time else ''}{s.title}".strip() for s in todays
    )
    return f"오늘은 {listing} 일정이 있어요."


def _build_coaching_message(
    chat_answer: str,
    todays: List[ScheduleRead],
    solutions: List[dict],
    reschedule_candidates: List[dict],
) -> str:
    """감정 공감 + 오늘 일정 요약 + 휴식/일정 조정 제안을 하나의 응답으로 합친다.

    ``chat_answer`` 는 ``chat_orchestrator``(기존 /chat/respond 파이프라인)가
    이미 만든 "공감 문장 + 최우선 해결책 + 확인 질문" 한 세트다(예: "일이 많아
    막막하게 느껴지는 마음이 이해돼요. 할 일을 3단계로 나누기 방법이 도움이
    될 수 있어요. ... 정리해볼까요?"). 여기에 음성 비서 전용으로 오늘 일정
    요약과, 있다면 그 밖의 대안 해결책/일정 조정 후보 수를 덧붙여 스펙이
    요구하는 3요소(공감·일정 요약·휴식/일정 조정 제안)를 항상 포함시킨다.
    ``chat_orchestrator``/``solution_recommender`` 자체는 건드리지 않는다.
    """
    parts: List[str] = []
    if chat_answer:
        parts.append(chat_answer.strip())
    parts.append(_schedule_summary_sentence(todays))

    extra_titles = [s.get("title") for s in solutions[1:3] if s.get("title")]
    if extra_titles:
        parts.append(f"그 밖에 {', '.join(extra_titles)}도 도움이 될 수 있어요.")

    if reschedule_candidates:
        parts.append(f"미룰 수 있는 일정 후보도 {len(reschedule_candidates)}개 찾아봤어요.")

    return " ".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# 1. reservation_recommendation — place/store discovery (NOT schedule_create)
# --------------------------------------------------------------------------- #
def _handle_reservation_recommendation(req: VoiceRouteRequest) -> VoiceRouteData:
    naver_ready = settings.naver_configured
    _logger.info(
        "[VOICE ROUTE] reservation_recommendation start text=%r naver_configured=%s",
        req.text, naver_ready,
    )
    try:
        data = place_recommendation_service.recommend_places({
            "user_id": req.user_id,
            "input": req.text,
            "current_datetime": req.current_datetime,
            "timezone": req.timezone,
            "location": req.location,
        })
    except (NaverConfigError, NaverApiError) as exc:
        _logger.warning(
            "[VOICE ROUTE] reservation_recommendation degraded (naver_configured=%s): %s",
            naver_ready, exc,
        )
        return VoiceRouteData(
            intent="reservation_recommendation",
            tts_text="지금은 추천 서비스에 연결할 수 없어요. 잠시 후 다시 시도해주세요.",
            screen_action=ScreenAction(
                type="navigate", target="reservation_recommendation", payload={}
            ),
            data={"recommended_places": [], "error": str(exc)},
        )

    places = data.recommended_places
    if places:
        tts_text = f"추천 후보를 찾아봤어요. {places[0].name} 등 {len(places)}곳을 화면에서 확인해보세요."
        _logger.info(
            "[VOICE ROUTE] reservation_recommendation success query=%r results=%d top=%r",
            data.query, len(places), places[0].name,
        )
    else:
        tts_text = "조건에 맞는 추천 장소를 찾지 못했어요. 다른 지역이나 종류로 다시 말씀해주세요."
        _logger.info(
            "[VOICE ROUTE] reservation_recommendation success query=%r results=0", data.query,
        )
    return VoiceRouteData(
        intent="reservation_recommendation",
        tts_text=tts_text,
        screen_action=ScreenAction(
            type="navigate", target="reservation_recommendation", payload={"query": data.query}
        ),
        data=data.model_dump(),
    )


# --------------------------------------------------------------------------- #
# 2. emotion_schedule_coaching — empathy + today's schedule + solutions
# --------------------------------------------------------------------------- #
def _handle_emotion_schedule_coaching(db: Session, req: VoiceRouteRequest) -> VoiceRouteData:
    user_id, _ = repo.ensure_default_owner(db)
    date_str = _today(req)
    todays = _todays_schedules(db, user_id, date_str)
    now_iso = _naive_now_iso(req)

    schedule_context = ScheduleContext(
        current_time=now_iso,
        today_schedule=[
            ScheduleEvent(
                id=s.id, title=s.title, category=s.category, priority=s.priority,
                start_time=f"{s.date}T{s.start_time}:00",
                end_time=f"{s.date}T{s.end_time or s.start_time}:00",
                is_fixed=False,
            )
            for s in todays if s.start_time
        ],
    )
    # 학습된 선호(집중 시간대)를 user_profile 로 전달 → reschedule 추천 점수에 반영.
    learned = memory_service.build_recommendation_profile(db, user_id)
    blocks = learned.get("preferred_time_blocks")
    user_profile = UserProfile(preferred_time_blocks=blocks) if blocks else None
    chat_data = chat_orchestrator.respond(
        ChatRespondRequest(
            message=req.text, schedule_context=schedule_context, user_profile=user_profile,
        )
    )

    solutions_raw = [s.model_dump() for s in chat_data.solutions]
    reschedule_raw = [c.model_dump() for c in chat_data.reschedule_candidates]
    # 공감(chat_orchestrator) + 오늘 일정 요약 + 휴식/일정 조정 제안을 항상
    # 함께 담는다 — chat_data.tts_text 단독으로는 공감 문장만 짧게 나온다.
    tts_text = _build_coaching_message(chat_data.answer, todays, solutions_raw, reschedule_raw)
    action_buttons = sorted({b for s in chat_data.solutions for b in s.action_buttons}) or [
        "오늘 일정 보기", "휴식 추가", "일정 미루기", "알림 설정",
    ]
    return VoiceRouteData(
        intent="emotion_schedule_coaching",
        tts_text=tts_text,
        screen_action=ScreenAction(
            type="show_card", target="emotion_schedule_coaching",
            payload={"action_buttons": action_buttons},
        ),
        data={
            "answer": chat_data.answer,
            "today_schedule": [s.model_dump() for s in todays],
            "solutions": solutions_raw,
            "reschedule_candidates": reschedule_raw,
            "selected_solution_category": chat_data.selected_solution_category,
        },
    )


# --------------------------------------------------------------------------- #
# 3. daily_briefing
# --------------------------------------------------------------------------- #
def _handle_daily_briefing(db: Session, req: VoiceRouteRequest) -> VoiceRouteData:
    user_id, _ = repo.ensure_default_owner(db)
    date_str = _today(req)
    todays = _todays_schedules(db, user_id, date_str)
    todos = [t for t in todo_service.list_todos(db, user_id=user_id) if not t.completed]

    briefing_req = DailyBriefingRequest(
        date=date_str,
        schedules=[
            BriefingSchedule(
                title=s.title, category=s.category or "etc",
                start_time=s.start_time, end_time=s.end_time, priority=s.priority,
            )
            for s in todays
        ],
        todos=[BriefingTodo(title=t.title, priority=t.priority, is_done=t.completed) for t in todos],
    )
    # 사용자 음성 스타일(말투/길이/알림강도)을 브리핑 LLM 요약에 반영.
    prefs = {
        "assistant_tone": req.assistant_tone,
        "response_length": req.response_length,
        "reminder_strength": req.reminder_strength,
    }
    prefs = {k: v for k, v in prefs.items() if v}
    data = briefing_generator.generate_briefing(briefing_req, preferences=prefs or None)

    # 날씨 연동 지점(TODO): 실제 날씨 API 키가 연결되면 이 fallback 문구 대신
    # briefing_generator 쪽에서 날씨 문장을 만들어 tts_text에 포함시킨다.
    weather_note = "날씨 연동은 아직 준비 중이라 오늘 일정 중심으로 안내해드릴게요."
    tts_text = f"{data.tts_text} {weather_note}" if data.tts_text else weather_note
    return VoiceRouteData(
        intent="daily_briefing",
        tts_text=tts_text,
        screen_action=ScreenAction(type="show_card", target="daily_briefing", payload={}),
        data=data.model_dump(),
    )


# --------------------------------------------------------------------------- #
# 4. schedule_query
# --------------------------------------------------------------------------- #
def _handle_schedule_query(db: Session, req: VoiceRouteRequest) -> VoiceRouteData:
    user_id, _ = repo.ensure_default_owner(db)
    date_str = _today(req)
    todays = _todays_schedules(db, user_id, date_str)
    if todays:
        listing = ", ".join(f"{(s.start_time + ' ') if s.start_time else ''}{s.title}".strip() for s in todays)
        tts_text = f"오늘은 {listing} 일정이 있어요."
    else:
        tts_text = "오늘 등록된 일정이 없어요."
    return VoiceRouteData(
        intent="schedule_query",
        tts_text=tts_text,
        screen_action=ScreenAction(type="navigate", target="calendar", payload={"date": date_str}),
        data={"today_schedule": [s.model_dump() for s in todays]},
    )


# --------------------------------------------------------------------------- #
# 5. reminder_setting — only meaningful with a pending schedule_created context
# --------------------------------------------------------------------------- #
def _handle_reminder_setting(db: Session, req: VoiceRouteRequest, classified: dict) -> VoiceRouteData:
    ctx = req.context or {}
    schedule_id = ctx.get("schedule_id")
    item_type = ctx.get("item_type", "EVENT")

    if classified.get("reminder_decline"):
        return VoiceRouteData(
            intent="reminder_setting",
            tts_text="네, 알림 없이 진행할게요.",
            screen_action=ScreenAction(type="none", payload={}),
            data={"reminder_enabled": False},
        )

    minutes = classified.get("reminder_minutes")
    minutes_before = minutes if minutes is not None else _DEFAULT_REMINDER_MINUTES

    if not schedule_id or item_type != "EVENT":
        # TODO 항목이거나 대상 일정이 없으면(=이번 MVP 범위 밖) 안내만 하고 계획은 만들지 않는다.
        return VoiceRouteData(
            intent="reminder_setting",
            tts_text=f"알림을 {minutes_before}분 전으로 설정할게요.",
            screen_action=ScreenAction(type="none", payload={}),
            data={"reminder_enabled": True, "reminder_minutes_before": minutes_before},
        )

    sched = local_schedule_service.get_schedule(db, schedule_id)
    if sched is None:
        return VoiceRouteData(
            intent="reminder_setting",
            tts_text="방금 등록한 일정을 찾지 못해 알림을 설정하지 못했어요.",
            screen_action=ScreenAction(type="none", payload={}),
            data={"reminder_enabled": False},
        )

    user_id, _ = repo.ensure_default_owner(db)
    plan = notification_plan_builder.build_event_plan(
        db, sched, user_id=user_id, persist=True, custom_reminder_minutes=minutes_before,
    )
    return VoiceRouteData(
        intent="reminder_setting",
        tts_text=f"좋아요. 일정 {minutes_before}분 전에 알려드릴게요.",
        screen_action=ScreenAction(type="show_card", target="reminder_plan", payload={}),
        data={
            "reminder_enabled": True,
            "reminder_minutes_before": minutes_before,
            "reminder_plan": plan.model_dump(),
        },
    )


# --------------------------------------------------------------------------- #
# 6. schedule_create — same parser + persistence path as the existing voice
#    schedule screen, but registers immediately and offers a reminder confirm.
# --------------------------------------------------------------------------- #
def _augment_schedule_with_llm(parsed, req: VoiceRouteRequest):
    """규칙 파서가 놓친 '빈 필드만' enhanced 파서(rule-first + LLM 갭필 + 환각
    가드)로 보정한다. 규칙 결과가 항상 우선이며, 아래 조건에서만 LLM을 호출한다:

      - ``ENABLE_LLM_SCHEDULE_PARSE`` 가 켜져 있고
      - 규칙 결과에 날짜/시간/제목 중 하나라도 비어 있을 때(= 보정할 게 있을 때)

    이미 규칙으로 충분히 채워졌으면 LLM을 호출하지 않아 비용을 아낀다. LLM/네트워크
    실패 시 원본(규칙) 결과를 그대로 반환한다. 프론트로 나가는 응답 스키마는
    바뀌지 않는다(schedule_draft/missing_fields만 보정).
    """
    if not settings.ENABLE_LLM_SCHEDULE_PARSE:
        return parsed
    d = parsed.schedule_draft
    if d.date and d.start_time and d.title:
        return parsed  # 규칙이 다 채움 → LLM 미호출

    today = req.current_datetime[:10] if req.current_datetime else None
    try:
        enh, _ = parse_enhanced(EnhancedParseRequest(
            text=req.text, timezone=req.timezone or "Asia/Seoul",
            today=today, use_llm=True,
        ))
    except Exception:
        return parsed  # 어떤 실패든 규칙 결과 유지

    # 규칙 우선 — 규칙이 비운 필드에만 enhanced 값을 채운다.
    new_date = d.date or enh.date
    new_start = d.start_time or enh.start_time
    new_end = d.end_time or (enh.end_time if not d.start_time else None)
    new_title = d.title or (enh.title or "")
    new_location = d.location or enh.location
    updated_draft = d.model_copy(update={
        "date": new_date, "start_time": new_start, "end_time": new_end,
        "title": new_title, "location": new_location,
    })

    # 보정된 필드는 missing_fields 에서 제거.
    missing = [
        m for m in parsed.missing_fields
        if not (m == "date" and new_date)
        and not (m == "time" and new_start)
        and not (m == "title" and new_title)
    ]

    # 규칙이 unknown 이었는데 LLM 보정으로 채워졌으면 intent 승격.
    intent = parsed.intent
    if intent == "unknown" and new_title and new_date:
        item_type = getattr(enh.item_type, "value", str(enh.item_type))
        intent = "create_todo" if item_type == "TODO" else "create_schedule"

    return parsed.model_copy(update={
        "schedule_draft": updated_draft,
        "missing_fields": missing,
        "intent": intent,
    })


def _voice_prefs(req: VoiceRouteRequest) -> dict:
    """VoiceRouteRequest 의 음성 스타일 prefs 를 dict 로(빈 값 제외)."""
    prefs = {
        "assistant_tone": req.assistant_tone,
        "response_length": req.response_length,
        "reminder_strength": req.reminder_strength,
    }
    return {k: v for k, v in prefs.items() if v}


def _clarify_tts(category, title, missing, req: VoiceRouteRequest, fallback: str) -> str:
    """부족 정보 되묻기 문구를 build_clarification(말투/LLM 반영)로 생성. 실패 시 fallback."""
    try:
        clar = schedule_clarification.build_clarification(
            category=category or "default",
            title=title or None,
            missing_fields=[m for m in missing if m in ("date", "time", "title", "location")],
            preferences=_voice_prefs(req) or None,
        )
        return clar.get("tts_text") or fallback
    except Exception:
        return fallback


def _handle_schedule_create(db: Session, req: VoiceRouteRequest) -> VoiceRouteData:
    parsed = parse_schedule(ScheduleParseRequest(
        input=req.text, input_type="voice", current_datetime=req.current_datetime,
        timezone=req.timezone, assistant_tone=req.assistant_tone,
        response_length=req.response_length, reminder_strength=req.reminder_strength,
    ))
    # 규칙 우선 + LLM 갭필(enhanced). 플래그 꺼짐/실패 시 규칙 결과 그대로.
    parsed = _augment_schedule_with_llm(parsed, req)
    draft = parsed.schedule_draft
    registerable = (
        parsed.intent in ("create_schedule", "create_todo")
        and "date" not in parsed.missing_fields
        and "time" not in parsed.missing_fields
        and bool(draft.title)
    )
    if not registerable:
        # 멀티턴: 부족한 슬롯을 다음 턴에 채우도록 부분 draft 를 context 로 넘긴다.
        ask = _clarify_tts(
            draft.category, draft.title, parsed.missing_fields, req,
            parsed.tts_text or "날짜와 시간을 포함해서 다시 말씀해주세요.",
        )
        return VoiceRouteData(
            intent="schedule_create",
            tts_text=ask,
            screen_action=ScreenAction(type="show_card", target="schedule_draft", payload={}),
            data={"schedule_draft": draft.model_dump(), "missing_fields": parsed.missing_fields},
            context={
                "type": "schedule_pending",
                "draft": draft.model_dump(),
                "missing": parsed.missing_fields,
                "intent": parsed.intent,
            },
        )

    return _register_draft(db, parsed.intent, draft.model_dump())


def _register_draft(db: Session, intent: str, draft_dict: dict) -> VoiceRouteData:
    """정규화된 draft dict 를 기존 저장 로직으로 등록하고 성공 응답을 만든다.
    schedule_create/멀티턴 완성 양쪽에서 재사용한다(저장 로직 중복 제거)."""
    user_id, calendar_id = repo.ensure_default_owner(db)
    draft_input = ScheduleDraftInput(**draft_dict)
    try:
        if intent == "create_todo":
            created_todo = todo_service.create_todo_from_draft(db, draft_input, user_id=user_id)
            item_id, title, item_type = created_todo.id, created_todo.title, "TODO"
            created_payload = created_todo.model_dump()
        else:
            created_sched = local_schedule_service.create_schedule_from_draft(
                db, draft_input, user_id=user_id, calendar_id=calendar_id
            )
            item_id, title, item_type = created_sched.id, created_sched.title, "EVENT"
            created_payload = created_sched.model_dump()
    except ValueError as exc:
        return VoiceRouteData(
            intent="schedule_create",
            tts_text="일정을 저장하지 못했어요. 다시 말씀해주세요.",
            screen_action=ScreenAction(type="show_card", target="schedule_draft", payload={}),
            data={"error": str(exc)},
        )

    tts_text = f"{title} 일정을 추가했어요. 이 일정 전에 알림을 받을까요?"
    return VoiceRouteData(
        intent="schedule_create",
        tts_text=tts_text,
        screen_action=ScreenAction(
            type="show_card", target="schedule_created", payload={"item_id": item_id}
        ),
        data={"item_type": item_type, "item": created_payload},
        context={"type": "schedule_created", "schedule_id": item_id, "title": title, "item_type": item_type},
    )


# --------------------------------------------------------------------------- #
# 멀티턴: 부족 슬롯 이어받기 (schedule_pending)
# --------------------------------------------------------------------------- #
def _handle_schedule_followup(db: Session, req: VoiceRouteRequest, ctx: dict) -> VoiceRouteData:
    """직전 턴에서 정보가 부족했던 일정(context.type == schedule_pending)에 대해,
    이번 발화의 슬롯을 규칙 파서로 뽑아 부분 draft 에 '빈 필드만' 병합한다.
    완성되면 기존 저장 로직으로 등록, 여전히 부족하면 다시 되묻는다.
    새 대화 엔진 없이 pendingContext + 기존 parse/create 만 사용한다."""
    partial = dict(ctx.get("draft") or {})
    intent = ctx.get("intent") or "create_schedule"

    newp = parse_schedule(ScheduleParseRequest(
        input=req.text, input_type="voice", current_datetime=req.current_datetime,
        timezone=req.timezone,
    ))
    nd = newp.schedule_draft.model_dump()
    # 빈 필드만 채움(기존 부분 draft 우선).
    for k in ("date", "start_time", "end_time", "location", "category"):
        if nd.get(k) and not partial.get(k):
            partial[k] = nd[k]
    # 제목이 아직 없으면 이번 발화의 제목을 사용.
    if not partial.get("title") and nd.get("title"):
        partial["title"] = nd["title"]

    is_todo = intent == "create_todo"
    has_title = bool(partial.get("title"))
    has_date = bool(partial.get("date"))
    has_time = bool(partial.get("start_time"))
    complete = has_title and has_date and (is_todo or has_time)

    if complete:
        return _register_draft(db, intent, partial)

    # 아직 부족 → 무엇이 비었는지 안내하고 pending 유지.
    missing = []
    if not has_date:
        missing.append("date")
    if not is_todo and not has_time:
        missing.append("time")
    if not has_title:
        missing.append("title")
    default_ask = "날짜를 알려주세요." if "date" in missing else (
        "시간을 알려주세요." if "time" in missing else "무슨 일정인지 알려주세요.")
    ask = _clarify_tts(partial.get("category"), partial.get("title"), missing, req, default_ask)
    return VoiceRouteData(
        intent="schedule_create",
        tts_text=ask,
        screen_action=ScreenAction(type="show_card", target="schedule_draft", payload={}),
        data={"schedule_draft": partial, "missing_fields": missing},
        context={"type": "schedule_pending", "draft": partial, "missing": missing, "intent": intent},
    )


# --------------------------------------------------------------------------- #
# 멀티턴: 직전 일정 수정 지시 ("아까 그거 오후로 바꿔줘")
# --------------------------------------------------------------------------- #
_MODIFY_SIGNALS = ("바꿔", "변경", "수정", "말고", "옮겨", "미뤄", "당겨", "로 해")


def _llm_modify_slots(text: str, ctx: dict) -> dict:
    """모호한 수정 참조에서 새 날짜/시간을 LLM으로 해석(규칙이 못 잡을 때만).
    반환: {"date"?, "start_time"?} (없으면 {}). 실패/비활성 시 {}."""
    if not (settings.ENABLE_LLM_MULTITURN and llm_service.is_enabled()):
        return {}
    prompt = (
        f"직전 일정: {ctx.get('title')} (id={ctx.get('schedule_id')})\n"
        f"사용자 수정 발화: \"{text}\"\n"
        "이 발화가 가리키는 새 날짜/시간만 JSON으로. 모르면 null.\n"
        '형식: {"date": "YYYY-MM-DD"|null, "start_time": "HH:MM"|null}'
    )
    data = llm_service.generate_json(prompt, system="너는 일정 수정 해석기야. 날짜/시간만 JSON으로.", temperature=0.0)
    out = {}
    if isinstance(data, dict):
        if isinstance(data.get("date"), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", data["date"]):
            out["date"] = data["date"]
        if isinstance(data.get("start_time"), str) and re.match(r"^\d{2}:\d{2}$", data["start_time"]):
            out["start_time"] = data["start_time"]
    return out


def _shift_end_time(db: Session, schedule_id: str, new_start: str) -> Optional[str]:
    """새 시작 시간에 맞춰 종료 시간을 기존 소요시간만큼 이동해 반환("HH:mm").
    기존 종료가 없거나 자정을 넘기는 경우 None(종료 미변경)."""
    from datetime import datetime, timedelta

    def _p(t: str) -> datetime:
        return datetime.strptime(t, "%H:%M")

    dur = timedelta(hours=1)
    try:
        cur = local_schedule_service.get_schedule(db, schedule_id)
    except Exception:
        cur = None
    if cur and cur.start_time and cur.end_time:
        try:
            d = _p(cur.end_time) - _p(cur.start_time)
            if d.total_seconds() > 0:
                dur = d
        except ValueError:
            pass
    try:
        ns = _p(new_start)
    except ValueError:
        return None
    ne = ns + dur
    if ne.day != ns.day or ne <= ns:  # 자정 넘김 방지
        return None
    return ne.strftime("%H:%M")


def _handle_schedule_modify(db: Session, req: VoiceRouteRequest, ctx: dict) -> VoiceRouteData:
    """직전에 만든 일정(context.type == schedule_created, EVENT)을 수정한다.
    새 시각/날짜는 규칙 파서로 우선 추출하고, 못 잡으면 LLM 해석(옵션)으로 보완.
    실제 변경은 기존 local_schedule_service.update_schedule(PATCH)만 사용한다."""
    schedule_id = ctx.get("schedule_id")
    if not schedule_id or ctx.get("item_type") != "EVENT":
        return _handle_fallback_chat(req)

    p = parse_schedule(ScheduleParseRequest(
        input=req.text, input_type="voice",
        current_datetime=req.current_datetime, timezone=req.timezone,
    ))
    d = p.schedule_draft
    update = {}
    if d.date:
        update["date"] = d.date
    if d.start_time:
        update["start_time"] = d.start_time
    if d.end_time:
        update["end_time"] = d.end_time
    if not update:  # 규칙이 못 잡음 → LLM 해석(모호한 참조)
        update.update(_llm_modify_slots(req.text, ctx))

    # 시작 시간만 바뀌면 종료 시간도 함께 옮겨(기존 소요시간 유지) end>start 제약 위반 방지.
    if update.get("start_time") and not update.get("end_time"):
        shifted = _shift_end_time(db, schedule_id, update["start_time"])
        if shifted:
            update["end_time"] = shifted

    keep_ctx = {"type": "schedule_created", "schedule_id": schedule_id,
                "title": ctx.get("title"), "item_type": "EVENT"}
    if not update:
        return VoiceRouteData(
            intent="schedule_create",
            tts_text="어떻게 바꿀까요? 새 날짜나 시간을 알려주세요.",
            screen_action=ScreenAction(type="show_card", target="schedule_created",
                                       payload={"item_id": schedule_id}),
            data={}, context=keep_ctx,
        )
    try:
        updated = local_schedule_service.update_schedule(db, schedule_id, ScheduleUpdate(**update))
    except Exception:
        updated = None
    if updated is None:
        return VoiceRouteData(
            intent="schedule_create",
            tts_text="일정을 바꾸지 못했어요. 다시 말씀해주세요.",
            screen_action=ScreenAction(type="none", payload={}), data={}, context=keep_ctx,
        )
    when = f"{updated.date or ''} {updated.start_time or ''}".strip()
    return VoiceRouteData(
        intent="schedule_create",
        tts_text=f"{updated.title} 일정을 {when}로 바꿨어요." if when else f"{updated.title} 일정을 바꿨어요.",
        screen_action=ScreenAction(type="show_card", target="schedule_created",
                                   payload={"item_id": schedule_id}),
        data={"item_type": "EVENT", "item": updated.model_dump()},
        context=keep_ctx,
    )


# --------------------------------------------------------------------------- #
# 7. fallback_chat
# --------------------------------------------------------------------------- #
def _handle_fallback_chat(req: VoiceRouteRequest) -> VoiceRouteData:
    chat_data = chat_orchestrator.respond(ChatRespondRequest(message=req.text))
    tts_text = chat_data.tts_text or chat_data.answer
    return VoiceRouteData(
        intent="fallback_chat",
        tts_text=tts_text,
        screen_action=ScreenAction(type="none", payload={}),
        data={"answer": chat_data.answer},
    )


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def route(db: Session, req: VoiceRouteRequest) -> VoiceRouteData:
    text = (req.text or "").strip()
    if not text:
        return VoiceRouteData(
            intent="fallback_chat",
            tts_text="음성을 인식하지 못했어요. 다시 말씀해주세요.",
            screen_action=ScreenAction(type="none", payload={}),
            data={},
        )

    # 멀티턴 이어받기: 직전 턴이 '정보 부족한 일정'이었다면, 이번 발화를 부족 슬롯
    # 채우기로 우선 처리한다(의도 재분류보다 앞선다). 단, 사용자가 명백히 다른
    # 주제로 넘어가면(예약/브리핑/감정 등 명확 intent) 그쪽을 우선한다.
    if (req.context or {}).get("type") == "schedule_pending":
        pre = voice_intent_router.select_voice_intent(text, context=req.context)
        if pre.get("intent") in ("schedule_create", "fallback_chat"):
            try:
                result = _handle_schedule_followup(db, req, req.context)
            except Exception:
                _logger.exception("[VOICE ROUTE] followup failed text=%r", text)
                result = _handle_fallback_chat(req)
            result.debug = {"matched_keywords": {"schedule_pending": True}}
            return result

    # 멀티턴 수정: 직전에 만든 일정이 있고 "바꿔/변경/…" 같은 수정 지시가 오면
    # 기존 일정을 PATCH(수정)한다. (알림 응답 "응/네" 등은 신호가 없어 그대로 통과)
    if ((req.context or {}).get("type") == "schedule_created"
            and any(sig in text for sig in _MODIFY_SIGNALS)):
        try:
            result = _handle_schedule_modify(db, req, req.context)
        except Exception:
            _logger.exception("[VOICE ROUTE] modify failed text=%r", text)
            result = _handle_fallback_chat(req)
        result.debug = {"matched_keywords": {"schedule_modify": True}}
        return result

    classified = voice_intent_router.select_voice_intent_hybrid(text, context=req.context)
    intent = classified["intent"]
    _logger.info(
        "[VOICE ROUTE] text=%r intent=%s matched=%s",
        text, intent, classified.get("matched_keywords"),
    )

    try:
        if intent == "reservation_recommendation":
            result = _handle_reservation_recommendation(req)
        elif intent == "emotion_schedule_coaching":
            result = _handle_emotion_schedule_coaching(db, req)
        elif intent == "daily_briefing":
            result = _handle_daily_briefing(db, req)
        elif intent == "schedule_query":
            result = _handle_schedule_query(db, req)
        elif intent == "reminder_setting":
            result = _handle_reminder_setting(db, req, classified)
        elif intent == "schedule_create":
            result = _handle_schedule_create(db, req)
        else:
            result = _handle_fallback_chat(req)
    except Exception:
        _logger.exception("[VOICE ROUTE] handler failed for intent=%s text=%r", intent, text)
        result = VoiceRouteData(
            intent="fallback_chat",
            tts_text="죄송해요, 지금은 처리하지 못했어요. 다시 말씀해주시겠어요?",
            screen_action=ScreenAction(type="none", payload={}),
            data={},
        )

    # 대화형 턴에서 사용자 선호를 자동 학습(옵션). 게이팅/실패는 memory_service 내부에서
    # 처리되어 비활성/키없음이면 아무것도 하지 않는다. 결과 응답에는 영향 없음.
    if intent in ("fallback_chat", "emotion_schedule_coaching"):
        try:
            uid, _ = repo.ensure_default_owner(db)
            memory_service.extract_and_save_preference(db, uid, text)
        except Exception:
            _logger.exception("[VOICE ROUTE] preference auto-learn failed")

    result.debug = {"matched_keywords": classified.get("matched_keywords", {})}
    return result
