"""Rule-based life coaching CONNECTED to schedule / todo / free time / places /
reservations / personal preference.

NOT a new ML model, NO external psych/medical/map/reservation API, NO real LLM.
Reuses dashboard_service (today's context), reservation_recommender (free-slot
search), preference_service (personalization) and the emotion crisis keywords.
Coaching is supportive and NON-diagnostic. Never raises: everything degrades to
a neutral emotion + a default card.
"""

from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime
from datetime import time as dtime
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.life_coaching_schema import (
    CoachingCard,
    ContextSummary,
    DueTodo,
    FreeTimeSlot,
    LifeCoachingData,
    LifeCoachingRequest,
    NextSchedule,
    PlaceRecommendation,
    ReservationSuggestion,
    SafetyInfo,
)
from backend.database.schema.reservation_schema import (
    ExistingSchedule,
    ReservationCandidateRequest,
    ReservationConstraints,
)
from backend.services import dashboard_service, preference_service
from backend.services.emotion_analyzer import _rules as _emotion_rules
from backend.services.reservation_recommender import recommend_candidates

_DEFAULT_TZ = "Asia/Seoul"
_FREE_WINDOW = ("09:00", "21:00")
_FREE_DURATION = 30
_MAX_FREE_SLOTS = 2
_MAX_CARDS = 3

# extended state keywords (independent of the legacy emotion_rules to avoid
# regressing the locked /emotion/analyze contract). Tie broken by _ORDER.
_EMOTION_KEYWORDS = {
    "stress": ["스트레스", "압박", "마감", "부담", "힘들어", "벅차"],
    "tired": ["피곤", "지침", "지쳐", "지치", "졸려", "기운 없", "쉬고 싶"],
    "overwhelmed": ["머리 복잡", "머리가 복잡", "복잡해", "정신없", "할 게 너무 많", "할일이 너무 많"],
    "anxious": ["불안", "걱정", "초조", "긴장"],
    "sad": ["우울", "슬퍼", "속상", "외로워", "눈물"],
    "unmotivated": ["하기 싫", "의욕 없", "귀찮", "무기력"],
    "angry": ["짜증", "화나", "분노", "열받"],
    "positive": ["좋아", "행복", "뿌듯", "신나", "설레"],
}
_ORDER = ["stress", "tired", "overwhelmed", "anxious", "sad", "unmotivated", "angry", "positive"]

_EMOTION_ACTIONS = {
    "stress": ["break_down_task", "find_free_time", "rest"],
    "tired": ["rest", "recommend_place"],
    "overwhelmed": ["break_down_task", "reschedule", "find_free_time"],
    "anxious": ["prepare_now", "break_down_task", "encourage"],
    "sad": ["encourage", "recommend_place", "rest"],
    "unmotivated": ["start_small", "find_free_time", "encourage"],
    "angry": ["rest", "encourage"],
    "positive": ["prepare_now", "encourage"],
    "neutral": ["encourage", "find_free_time"],
}

_PLACES = {
    "tired": [("cafe", "조용한 카페", "피곤함이 감지되어 조용히 쉴 수 있는 장소를 추천합니다."),
              ("park", "가까운 산책로", "짧은 산책이 기분 전환에 도움이 될 수 있습니다.")],
    "stress": [("park", "가까운 산책로", "머리가 복잡할 때 짧은 산책이 도움이 될 수 있습니다."),
               ("cafe", "조용한 카페", "잠시 앉아 숨을 고를 수 있는 장소입니다.")],
    "overwhelmed": [("park", "가까운 산책로", "생각을 정리할 짧은 산책을 추천합니다.")],
    "sad": [("cafe", "따뜻한 카페", "따뜻한 음료와 함께 잠시 쉬어가기 좋은 장소입니다.")],
    "unmotivated": [("gym", "가벼운 운동 공간", "가벼운 움직임이 의욕 회복에 도움이 될 수 있습니다.")],
}

# emotion -> reservation category (mapped to EXISTING virtual-business categories)
_RESV = {
    "tired": ("pt", "가벼운 활동이나 휴식으로 컨디션을 회복할 수 있는 예약 후보입니다."),
    "stress": ("pt", "가벼운 운동으로 스트레스를 풀 수 있는 예약 후보입니다."),
    "unmotivated": ("studyroom", "집중 환경(스터디룸) 예약 후보로 작은 시작을 도울 수 있습니다."),
}
_BEAUTY_KEYWORDS = ("머리", "미용", "헤어", "네일", "파마", "염색")

_TONE_PREFIX = {"gentle": "괜찮아요. ", "warm": "많이 애쓰고 있어요. "}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _resolve_date(date: Optional[str], tz_name: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    if date:
        try:
            return date_cls.fromisoformat(date).isoformat(), warnings
        except (ValueError, TypeError):
            warnings.append("date 형식이 올바르지 않아 오늘 날짜로 대체했습니다.")
    try:
        tz = ZoneInfo(tz_name or _DEFAULT_TZ)
    except Exception:
        tz = None
    now = datetime.now(tz) if tz is not None else datetime.now()
    return now.date().isoformat(), warnings


def _classify(text: str, stress_triggers: List[str]) -> Tuple[str, List[str], float, bool]:
    """Return (primary, secondaries, score, stress_boosted)."""
    counts = {e: sum(1 for kw in kws if kw in text) for e, kws in _EMOTION_KEYWORDS.items()}

    stress_boosted = False
    for trig in stress_triggers or []:
        if trig and trig in text:
            counts["stress"] = counts.get("stress", 0) + 1
            stress_boosted = True

    detected = [e for e in _ORDER if counts.get(e, 0) > 0]
    if not detected:
        return "neutral", [], 0.5, stress_boosted

    detected.sort(key=lambda e: (-counts[e], _ORDER.index(e)))
    primary = detected[0]
    secondaries = detected[1:3]
    score = min(0.95, 0.55 + 0.12 * counts[primary] + 0.05 * len(secondaries))
    if stress_boosted:
        score = min(0.95, score + 0.05)
    return primary, secondaries, round(score, 2), stress_boosted


def _tone(pref, msg: str) -> str:
    return _TONE_PREFIX.get(pref.preferred_tone, "") + msg


def _hhmm_block(hhmm: str) -> str:
    return preference_service.time_block_of(hhmm) or "afternoon"


def _free_slots(schedules, date: str, avoid: set) -> List[FreeTimeSlot]:
    busy: List[ExistingSchedule] = []
    for s in schedules:
        if s.start_time and s.end_time:
            busy.append(ExistingSchedule(
                id=s.id, title=s.title, date=date,
                start_time=s.start_time, end_time=s.end_time,
            ))
    req = ReservationCandidateRequest(
        constraints=ReservationConstraints(
            target_date=date, preferred_start_time=_FREE_WINDOW[0],
            preferred_end_time=_FREE_WINDOW[1], duration_minutes=_FREE_DURATION,
        ),
        existing_schedules=busy,
    )
    result = recommend_candidates(req)
    slots: List[FreeTimeSlot] = []
    seen = set()
    for cand in result.recommended_candidates:
        block = _hhmm_block(cand.start_time)
        if block in avoid:
            continue
        if cand.start_time in seen:
            continue
        seen.add(cand.start_time)
        slots.append(FreeTimeSlot(
            date=date, start_time=cand.start_time, end_time=cand.end_time,
            recommended_activity="휴식",
            reason="일정 사이의 여유 시간입니다. 잠깐 쉬어가기 좋아요.",
        ))
        if len(slots) >= _MAX_FREE_SLOTS:
            break
    return slots


# --------------------------------------------------------------------------- #
# coaching card builders (return None when not applicable for the context)
# --------------------------------------------------------------------------- #
def _card(action: str, pref, *, free_slots, due_todos, next_sched, schedule_count) -> Optional[CoachingCard]:
    if action == "rest":
        if free_slots:
            fs = free_slots[0]
            msg = f"오늘 일정 사이 {fs.start_time}~{fs.end_time}에 잠깐 쉬어가면 좋아요."
        else:
            msg = "5분만이라도 눈을 감고 숨을 고르는 짧은 휴식을 추천해요."
        return CoachingCard(action_type="rest", title="짧은 휴식 추천",
                            message=_tone(pref, msg),
                            reason="피로/스트레스 표현이 감지되어 잠깐의 휴식을 제안합니다.")
    if action == "find_free_time":
        if not free_slots:
            return None
        fs = free_slots[0]
        return CoachingCard(action_type="find_free_time", title="빈 시간 활용",
                            message=_tone(pref, f"{fs.start_time}~{fs.end_time}에 여유가 있어요. 이 시간을 활용해보세요."),
                            reason="오늘 일정 사이에 빈 시간이 있습니다.")
    if action == "break_down_task":
        extra = f" 오늘 마감인 '{due_todos[0].title}'부터 시작해보면 좋아요." if due_todos else ""
        return CoachingCard(action_type="break_down_task", title="할 일 작게 나누기",
                            message=_tone(pref, "할 일을 10분 안에 할 수 있는 작은 단위로 나눠 시작해보세요." + extra),
                            reason="할 일이 많을 때는 작게 나누면 부담이 줄어듭니다.")
    if action == "reschedule":
        if schedule_count < 3:
            return None
        return CoachingCard(action_type="reschedule", title="일정 조정 제안",
                            message=_tone(pref, "오늘 일정이 많아 보여요. 급하지 않은 일정은 다른 날로 옮겨보는 것도 방법이에요."),
                            reason="오늘 일정이 많아 부담을 줄이기 위한 제안입니다.")
    if action == "start_small":
        return CoachingCard(action_type="start_small", title="작게 시작하기",
                            message=_tone(pref, "딱 10분만, 가장 쉬운 것부터 시작해볼까요?"),
                            reason="의욕이 낮을 때는 작은 시작이 도움이 됩니다.")
    if action == "prepare_now":
        if next_sched is None:
            return None
        when = f" ({next_sched.start_time})" if next_sched.start_time else ""
        return CoachingCard(action_type="prepare_now", title="다음 일정 준비",
                            message=_tone(pref, f"곧 '{next_sched.title}'{when} 일정이 있어요. 미리 가볍게 준비해두면 마음이 편해요."),
                            reason="다음 일정이 있어 미리 준비를 제안합니다.")
    if action == "recommend_place":
        return CoachingCard(action_type="recommend_place", title="장소 추천",
                            message=_tone(pref, "잠깐 다녀올 만한 조용한 장소를 추천해드릴 수 있어요."),
                            reason="기분 전환에 도움이 될 장소를 제안합니다.")
    if action == "recommend_reservation":
        return CoachingCard(action_type="recommend_reservation", title="예약 후보 추천",
                            message=_tone(pref, "원한다면 빈 시간에 맞춰 예약 후보를 찾아볼 수 있어요."),
                            reason="빈 시간에 맞춘 예약 후보를 제안합니다.")
    if action == "encourage":
        tail = "천천히 함께 해봐요." if pref.coaching_style in ("supportive", "coaching") else "지금 할 수 있는 것부터 해봐요."
        return CoachingCard(action_type="encourage", title="응원",
                            message=_tone(pref, f"오늘 하루도 충분히 잘 하고 있어요. {tail}"),
                            reason="지지적인 응원 메시지입니다.")
    return None


# --------------------------------------------------------------------------- #
# public
# --------------------------------------------------------------------------- #
def coach(db: Session, req: LifeCoachingRequest) -> LifeCoachingData:
    text = req.text or ""
    eff = preference_service.get_effective_user_preference(db, req.user_id)
    pref, meta = eff["preference"], eff["meta"]
    used: List[str] = []

    date, warnings = _resolve_date(req.date, req.timezone)

    # 1) emotion classification (+stress_trigger boost)
    primary, secondaries, score, stress_boosted = _classify(text, pref.stress_triggers)
    if stress_boosted:
        used.append("stress_triggers")

    # 2) today's context (reuse dashboard aggregation)
    try:
        today = dashboard_service.get_today(
            db, date=date, current_datetime=f"{date}T00:00", user_id=req.user_id
        )
        schedules, todos = today.schedules, today.todos
        nxt = today.next_schedule
    except Exception:
        schedules, todos, nxt = [], [], None
        warnings.append("오늘 일정을 불러오지 못해 기본 코칭으로 진행합니다.")

    next_sched = NextSchedule(title=nxt.title, start_time=nxt.start_time) if nxt else None
    due_todos = [DueTodo(title=t.title, due_date=t.due_date) for t in todos if t.due_date == date]
    context = ContextSummary(
        date=date, schedule_count=len(schedules), todo_count=len(todos),
        next_schedule=next_sched, due_todos=due_todos,
    )

    # 3) crisis / safety check (before anything else)
    crisis = any(k in text for k in _emotion_rules().get("crisis_keywords", []))
    if crisis:
        safety = SafetyInfo(
            risk_level="high",
            support_message=(
                "지금 안전이 가장 중요해요. 혼자 견디기 어렵다면 믿을 수 있는 사람이나 "
                "긴급 도움을 받을 수 있는 곳에 바로 연락해주세요."
            ),
        )
        card = CoachingCard(
            action_type="encourage", title="지금은 도움을 받는 게 좋아요",
            message="많이 힘든 마음이 느껴져요. 혼자 감당하지 말고 가까운 사람이나 전문가와 이야기해보세요.",
            reason="안전이 우선입니다.",
        )
        meta.used_preferences = _dedupe(used)
        return LifeCoachingData(
            input_text=text, primary_emotion=primary, secondary_emotions=secondaries,
            emotion_score=score, context_summary=context, coaching_cards=[card],
            free_time_slots=[], place_recommendations=[], reservation_suggestions=[],
            personalization=meta, safety=safety, warnings=warnings,
        )

    # 4) free time (reuse rule-based recommender)
    avoid = set(pref.avoid_times or [])
    if avoid:
        used.append("avoid_times")
    free_slots = _free_slots(schedules, date, avoid)

    # 5) coaching cards from the emotion's action list, tuned by context/preference
    actions = list(_EMOTION_ACTIONS.get(primary, _EMOTION_ACTIONS["neutral"]))
    if due_todos and "break_down_task" not in actions:
        actions.insert(0, "break_down_task")

    rest_disabled = not pref.rest_recommendation_enabled
    if rest_disabled:
        used.append("rest_recommendation_enabled")

    if pref.preferred_tone in _TONE_PREFIX:
        used.append("preferred_tone")
    if pref.coaching_style:
        used.append("coaching_style")

    cards: List[CoachingCard] = []
    seen_types = set()
    for action in actions:
        if action == "rest" and rest_disabled:
            action = "find_free_time"   # substitute a non-rest action
        if action in seen_types:
            continue
        card = _card(action, pref, free_slots=free_slots, due_todos=due_todos,
                     next_sched=next_sched, schedule_count=len(schedules))
        if card is not None:
            cards.append(card)
            seen_types.add(card.action_type)
        if len(cards) >= _MAX_CARDS:
            break

    # fallback: guarantee at least one card
    if not cards:
        cards.append(_card("encourage", pref, free_slots=free_slots, due_todos=due_todos,
                           next_sched=next_sched, schedule_count=len(schedules)))
    # fallback rest card when no free slot and a rest-type emotion
    if not free_slots and primary in ("tired", "stress", "overwhelmed") and not rest_disabled \
            and not any(c.action_type == "rest" for c in cards):
        cards.append(CoachingCard(
            action_type="rest", title="짧은 휴식 추천",
            message=_tone(pref, "빈 시간이 많지 않아도 5분 정도 짧게 쉬어가는 걸 추천해요."),
            reason="빈 시간이 부족해 짧은 휴식을 대신 제안합니다.",
        ))

    # 6) place recommendations (rule-based; NOT a map API)
    places = [PlaceRecommendation(place_type=p, name=n, reason=r)
              for p, n, r in _PLACES.get(primary, [])]

    # 7) reservation suggestions (hint into the existing candidates endpoint)
    reservations: List[ReservationSuggestion] = []
    time_pref = _hhmm_block(free_slots[0].start_time) if free_slots else (
        (pref.preferred_reservation_times or ["afternoon"])[0]
    )
    if any(k in text for k in _BEAUTY_KEYWORDS) and "머리 복잡" not in text and "머리가 복잡" not in text:
        cat = "nail" if "네일" in text else "hair"
        reservations.append(ReservationSuggestion(
            category=cat, time_preference=time_pref,
            reason="자기 관리 관련 표현이 있어 미용 예약 후보를 확인할 수 있습니다."))
    elif primary in _RESV:
        cat, reason = _RESV[primary]
        reservations.append(ReservationSuggestion(category=cat, time_preference=time_pref, reason=reason))
        if free_slots or pref.preferred_reservation_times:
            used.append("preferred_reservation_times")

    meta.used_preferences = _dedupe(used)
    if meta.personalization_applied:
        meta.reason = "말투·코칭 스타일과 선호 시간대를 반영했습니다."

    return LifeCoachingData(
        input_text=text, primary_emotion=primary, secondary_emotions=secondaries,
        emotion_score=score, context_summary=context, coaching_cards=cards[:_MAX_CARDS],
        free_time_slots=free_slots, place_recommendations=places,
        reservation_suggestions=reservations, personalization=meta,
        safety=SafetyInfo(), warnings=warnings,
    )


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
