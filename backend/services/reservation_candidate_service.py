"""Virtual-business reservation recommendation + booking (MVP, mock-only).

This layer sits on top of the existing rule-based engine and DB services and
adds nothing external:

  * candidate generation delegates the conflict math to
    ``reservation_recommender.recommend_candidates`` (minutes-based, safe;
    touching intervals like 14:00-15:00 / 15:00-16:00 do NOT conflict);
  * "busy" = the user's SAVED schedules for the date + the business'
    ``reserved_slots``;
  * booking reuses ``local_schedule_service.create_schedule`` so a chosen
    candidate lands in the same planner_items / event_details store as any
    other local schedule.

Everything degrades safely: bad input yields empty candidates (HTTP 200), and
only booking (which mutates) raises ValueError for the router to turn into 422.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.local_schedule_schema import ScheduleCreate, ScheduleRead
from backend.database.schema.reservation_business_schema import (
    BusinessAlternative,
    BusinessCandidate,
    BusinessCandidateData,
    BusinessCandidateRequest,
    ReservationBookingRequest,
    VirtualBusiness,
)
from backend.database.schema.reservation_schema import (
    ExistingSchedule,
    ReservationCandidateRequest,
    ReservationConstraints,
)
from backend.services import local_schedule_service as sched_service
from backend.services import planner_mapping as pm
from backend.services import virtual_business_service as biz_service
from backend.services.reservation_recommender import recommend_candidates

# time_preference -> (window_start, window_end) in 'HH:mm'. "any" resolves to
# the business' full operating hours at call time.
_PREF_WINDOWS = {
    "morning": ("09:00", "12:00"),
    "afternoon": ("12:00", "18:00"),
    "evening": ("18:00", "21:00"),
}
_PREF_LABEL = {
    "morning": "오전",
    "afternoon": "오후",
    "evening": "저녁",
    "any": "운영 시간 내",
}
_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_INACTIVE_STATUSES = {"CANCELLED", "DELETED"}


# --------------------------------------------------------------------------- #
# small time helpers (all comparisons are int-minutes, never string compares)
# --------------------------------------------------------------------------- #
def _to_min(hhmm: str) -> Optional[int]:
    if not pm.valid_hhmm(hhmm):
        return None
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _weekday(date_str: str) -> Optional[str]:
    """'YYYY-MM-DD' -> 'MON'..'SUN', or None if unparseable."""
    try:
        return _WEEKDAYS[date_cls.fromisoformat(date_str).weekday()]
    except (ValueError, TypeError):
        return None


def _window_for(pref: str, business: VirtualBusiness) -> Optional[Tuple[str, str]]:
    """Preferred window clamped to the business' operating hours.

    Returns ('HH:mm', 'HH:mm') or None when the intersection is empty/invalid.
    """
    open_m, close_m = _to_min(business.open_time), _to_min(business.close_time)
    if open_m is None or close_m is None or open_m >= close_m:
        return None
    if pref == "any" or pref not in _PREF_WINDOWS:
        start_m, end_m = open_m, close_m
    else:
        ws, we = _PREF_WINDOWS[pref]
        start_m = max(open_m, _to_min(ws))
        end_m = min(close_m, _to_min(we))
    if start_m >= end_m:
        return None
    return f"{start_m // 60:02d}:{start_m % 60:02d}", f"{end_m // 60:02d}:{end_m % 60:02d}"


# --------------------------------------------------------------------------- #
# busy intervals: user's SAVED schedules for the date
# --------------------------------------------------------------------------- #
def _stored_busy(db: Session, user_id: str, date: str) -> List[ExistingSchedule]:
    """Active stored EVENTs on `date` as busy intervals (skip cancelled/all-day/bad)."""
    busy: List[ExistingSchedule] = []
    for item in repo.list_events_by_date(db, user_id=user_id, date=date):
        if (item.status or "").upper() in _INACTIVE_STATUSES:
            continue
        ev = item.event_detail
        if ev is None or not ev.start_at or not ev.end_at:
            continue
        start, end = pm.time_from_dt(ev.start_at), pm.time_from_dt(ev.end_at)
        if not pm.valid_hhmm(start) or not pm.valid_hhmm(end):
            continue
        busy.append(ExistingSchedule(
            id=item.item_id, title=item.title, date=date,
            start_time=start, end_time=end,
        ))
    return busy


# --------------------------------------------------------------------------- #
# candidate collection for a single (date, preference) across target businesses
# --------------------------------------------------------------------------- #
def _target_businesses(req: BusinessCandidateRequest) -> List[VirtualBusiness]:
    if req.business_id:
        b = biz_service.get_business(req.business_id)
        return [b] if b else []
    return biz_service.list_by_category(req.category)


def _collect(
    db: Session,
    req: BusinessCandidateRequest,
    *,
    date: str,
    pref: str,
    user_busy: List[ExistingSchedule],
) -> List[BusinessCandidate]:
    """All conflict-free candidates for the given date/preference across businesses."""
    weekday = _weekday(date)
    label = _PREF_LABEL.get(pref, "")
    out: List[BusinessCandidate] = []

    for business in _target_businesses(req):
        # skip closed days
        if weekday is not None and weekday in [d.upper() for d in business.closed_days]:
            continue

        window = _window_for(pref, business)
        if window is None:
            continue
        win_start, win_end = window

        # None -> use the business default; an explicit non-positive value is invalid
        duration = (
            business.default_service_duration_minutes
            if req.duration_minutes is None
            else req.duration_minutes
        )
        if not duration or duration <= 0:
            continue

        # busy = user's saved schedules + this business' reserved slots on `date`
        busy = list(user_busy)
        for slot in business.reserved_slots:
            if slot.date != date:
                continue
            if not pm.valid_hhmm(slot.start_time) or not pm.valid_hhmm(slot.end_time):
                continue
            busy.append(ExistingSchedule(
                id=business.business_id, title=f"{business.name} 예약",
                date=date, start_time=slot.start_time, end_time=slot.end_time,
            ))

        rc_req = ReservationCandidateRequest(
            constraints=ReservationConstraints(
                target_date=date,
                preferred_start_time=win_start,
                preferred_end_time=win_end,
                duration_minutes=duration,
                category=req.category,
            ),
            existing_schedules=busy,
        )
        result = recommend_candidates(rc_req)

        # honor the business' slot granularity: keep starts aligned to open_time
        open_m = _to_min(business.open_time)
        interval = business.slot_interval_minutes or 30
        for cand in result.recommended_candidates:
            start_m = _to_min(cand.start_time)
            if start_m is None:
                continue
            if open_m is not None and interval > 0 and (start_m - open_m) % interval != 0:
                continue
            out.append(BusinessCandidate(
                business_id=business.business_id,
                business_name=business.name,
                category=business.category,
                date=date,
                start_time=cand.start_time,
                end_time=cand.end_time,
                reason=(
                    f"{business.name}에서 사용자 일정과 업체 예약 현황이 "
                    f"겹치지 않는 {label} 시간입니다."
                ),
            ))

    # earliest first (closest to the start of the preferred window), stable by business
    out.sort(key=lambda c: (_to_min(c.start_time) or 0, c.business_id))
    return out


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def recommend_business_candidates(
    db: Session, req: BusinessCandidateRequest
) -> BusinessCandidateData:
    """Recommend reservation candidates for a category on a date, honoring the
    user's saved schedules, each business' hours / closed days / reserved slots,
    and the requested time-of-day preference. Never raises."""
    user_busy = _stored_busy(db, req.user_id, req.date)
    candidates = _collect(db, req, date=req.date, pref=req.time_preference, user_busy=user_busy)

    if candidates:
        req_label = _PREF_LABEL.get(req.time_preference, "")
        candidates[0].reason = (
            f"{candidates[0].business_name}에서 사용자 일정과 업체 예약 현황이 겹치지 않는 "
            f"가장 빠른 {req_label} 시간입니다."
        )
        return BusinessCandidateData(requested=req, candidates=candidates, alternatives=[])

    return BusinessCandidateData(
        requested=req, candidates=[],
        alternatives=_alternatives(db, req, user_busy),
    )


def _alternatives(
    db: Session, req: BusinessCandidateRequest, user_busy: List[ExistingSchedule]
) -> List[BusinessAlternative]:
    """When nothing fits: suggest sibling time windows on the same date first,
    then the same preference on upcoming dates. Bounded and safe."""
    alts: List[BusinessAlternative] = []
    req_label = _PREF_LABEL.get(req.time_preference, "")

    # 1) other time-of-day windows, same date
    if req.time_preference != "any":
        for alt_pref in ("morning", "afternoon", "evening"):
            if alt_pref == req.time_preference:
                continue
            if _collect(db, req, date=req.date, pref=alt_pref, user_busy=user_busy):
                alts.append(BusinessAlternative(
                    date=req.date, time_preference=alt_pref,
                    reason=(
                        f"{req_label} 시간대는 예약이 어려워 "
                        f"{_PREF_LABEL[alt_pref]} 시간대를 확인해볼 수 있습니다."
                    ),
                ))

    # 2) same preference on the next few days (first match only)
    if not alts:
        try:
            base = date_cls.fromisoformat(req.date)
        except (ValueError, TypeError):
            base = None
        if base is not None:
            for offset in range(1, 8):
                nxt = (base.toordinal() + offset)
                nxt_str = date_cls.fromordinal(nxt).isoformat()
                nxt_busy = _stored_busy(db, req.user_id, nxt_str)
                if _collect(db, req, date=nxt_str, pref=req.time_preference, user_busy=nxt_busy):
                    alts.append(BusinessAlternative(
                        date=nxt_str, time_preference=req.time_preference,
                        reason=(
                            f"{req.date}에는 {req_label} 예약이 어려워 "
                            f"{nxt_str}의 {req_label} 시간대를 확인해볼 수 있습니다."
                        ),
                    ))
                    break
    return alts


def book_reservation(db: Session, req: ReservationBookingRequest) -> ScheduleRead:
    """Persist a chosen candidate as a local schedule (EVENT), reusing the
    existing schedule service. Not a real booking — MVP only.

    Raises ValueError (router -> 422) for invalid times so the DB CHECK
    constraint never surfaces as a 500."""
    if not pm.valid_hhmm(req.start_time) or not pm.valid_hhmm(req.end_time):
        raise ValueError("start_time / end_time 포맷이 올바르지 않습니다 (HH:mm).")
    s, e = _to_min(req.start_time), _to_min(req.end_time)
    if s is None or e is None or s >= e:
        raise ValueError("end_time은 start_time보다 뒤여야 합니다.")

    business = biz_service.get_business(req.business_id)
    location = business.address if business else None

    payload = ScheduleCreate(
        title=f"{req.business_name} 예약",
        date=req.date,
        start_time=req.start_time,
        end_time=req.end_time,
        category=req.category or (business.category if business else None),
        priority="medium",
        location=location,
        memo=req.memo,
        source="ai",
    )
    user_id, calendar_id = repo.ensure_default_owner(db)
    return sched_service.create_schedule(db, payload, user_id=user_id, calendar_id=calendar_id)
