"""Rule-based departure / preparation planner.

Two independent entry points share this module:

  * build_departure_plan(req)              -> legacy leave_time/checklist/
                                              notifications (UNCHANGED).
  * build_departure_plan_with_travel(req)  -> travel-aware `alert_plan` shape,
                                              used only when options.
                                              include_travel_time is set.

Both never raise: malformed input yields a safe partial response. Maps failures
in the travel path degrade to a buffer-only departure time (travel = null).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.database.schema.alert_schema import (
    AlertOptions,
    AlertPlan,
    ChecklistItem,
    DepartureAlertPlanData,
    DeparturePlanData,
    DeparturePlanRequest,
    NotificationItem,
    TravelAwareReminder,
    UserProfile,
)
from backend.database.schema.travel_schema import TravelInfo
from backend.services import naver_maps_client as maps
from backend.services import travel_time_service as travel_svc

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


@lru_cache(maxsize=1)
def _checklist_rules() -> dict:
    with open(_RULES_DIR / "checklist_rules.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _notification_rules() -> dict:
    with open(_RULES_DIR / "notification_rules.json", encoding="utf-8") as f:
        return json.load(f)


def _wa_gwa(word: str) -> str:
    if not word:
        return "와"
    last = word[-1]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - 0xAC00) % 28 else "와"
    return "와"


def _eul_reul(word: str) -> str:
    if not word:
        return "를"
    last = word[-1]
    if "가" <= last <= "힣":
        return "을" if (ord(last) - 0xAC00) % 28 else "를"
    return "를"


def _to_min(hhmm: str) -> Optional[int]:
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def _to_hhmm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _build_checklist(category: str, weather: Optional[str]) -> List[ChecklistItem]:
    """Category base items + weather extras, de-duplicated by item name."""
    rules = _checklist_rules()
    cats = rules.get("categories", {})
    raw = list(cats.get(category, cats.get("etc", [])))
    if weather:
        raw += rules.get("weather", {}).get(weather.lower(), [])

    items: List[ChecklistItem] = []
    seen: set[str] = set()
    for x in raw:
        name = x.get("item")
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(ChecklistItem(**x))
    return items


def _items_phrase(checklist: List[ChecklistItem]) -> str:
    names = [c.item for c in checklist[:2]]
    if not names:
        return "필요한 준비물"
    if len(names) == 1:
        a = names[0]
        return f"{a}{_eul_reul(a)}"
    a, b = names[0], names[1]
    return f"{a}{_wa_gwa(a)} {b}{_eul_reul(b)}"


def _prep_message(offset: int, title: str, phrase: str) -> str:
    if offset >= 60:
        return f"{title} 준비를 시작할 시간입니다. {phrase} 미리 챙겨두세요."
    return f"{title} 시간이 다가옵니다. {phrase} 챙기고 출발을 준비하세요."


def _build_notifications(
    start_min: int,
    leave_min: int,
    pref,
    phrase: str,
    title: str,
) -> List[NotificationItem]:
    rules = _notification_rules()
    styles = rules.get("styles", {})

    # Forgetful users are escalated to the stronger style.
    style_name = pref.notification_style
    if pref.forgetful:
        style_name = rules.get("escalate_when_forgetful", "strong")
    style = styles.get(style_name, styles.get("normal", {}))

    # minute -> message (dict de-dupes identical times automatically)
    by_time: Dict[int, str] = {}

    # 1) reminders before the schedule start
    for off in style.get("before_start_minutes", []):
        t = start_min - off
        if t >= 0:
            by_time[t] = _prep_message(off, title, phrase)

    # 2) the departure (leave-time) reminder wins on any time collision
    if style.get("notify_at_leave", True):
        by_time[leave_min] = f"{_to_hhmm(leave_min)}에 출발하면 {title} 시간에 맞출 수 있습니다."

    # 3) forgetful: stronger PRE-START reminders (escalated above) plus one
    #    extra pre-departure nudge. Preserves prior forgetful behavior.
    if pref.forgetful:
        extra = rules.get("forgetful_extra_minutes_before_leave", 10)
        t = leave_min - extra
        if t >= 0 and t not in by_time:
            by_time[t] = f"곧 출발해야 합니다. {phrase} 다시 한 번 확인하세요."

    # 4) late_prone: DEPARTURE reminders that are earlier and more frequent.
    if getattr(pref, "late_prone", False):
        offsets = rules.get("late_prone_minutes_before_leave", [20, 10])
        if isinstance(offsets, int):
            offsets = [offsets]
        for off in sorted(set(offsets), reverse=True):
            t = leave_min - off
            if t >= 0 and t not in by_time:
                by_time[t] = f"출발 {off}분 전입니다. {phrase} 미리 챙기고 일찍 나설 준비를 하세요."

    return [
        NotificationItem(time=_to_hhmm(t), message=by_time[t])
        for t in sorted(by_time)
    ]


def build_departure_plan(req: DeparturePlanRequest) -> DeparturePlanData:
    """LEGACY planner — unchanged behavior/response contract."""
    sch, ctx, pref = req.schedule, req.context, req.user_preference

    checklist = _build_checklist((sch.category or "etc").lower(), ctx.weather)

    start_min = _to_min(sch.start_time)
    travel = max(0, ctx.estimated_travel_minutes)
    buffer = max(0, ctx.buffer_minutes)

    if start_min is None:
        return DeparturePlanData(
            leave_time=None,
            estimated_travel_minutes=travel,
            buffer_minutes=buffer,
            checklist=checklist,
            notifications=[],
        )

    leave_min = max(0, start_min - travel - buffer)
    leave_time = _to_hhmm(leave_min)

    notifications = _build_notifications(
        start_min, leave_min, pref, _items_phrase(checklist), sch.title
    )

    return DeparturePlanData(
        leave_time=leave_time,
        estimated_travel_minutes=travel,
        buffer_minutes=buffer,
        checklist=checklist,
        notifications=notifications,
    )


# --------------------------------------------------------------------------- #
# Travel-aware planner (additive; only used when options.include_travel_time)
# --------------------------------------------------------------------------- #
def _tzinfo_from(current_datetime: Optional[str]) -> timezone:
    """Timezone from the request's current_datetime; default KST (+09:00)."""
    if current_datetime:
        try:
            dt = datetime.fromisoformat(current_datetime.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                return dt.tzinfo  # type: ignore[return-value]
        except ValueError:
            pass
    return timezone(timedelta(hours=9))


def _fallback_date(current_datetime: Optional[str]):
    if current_datetime:
        try:
            return datetime.fromisoformat(current_datetime.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _iso_at(date_str, minutes, tzinfo, fallback_dt) -> Optional[str]:
    if minutes is None:
        return None
    y = m = d = None
    if date_str:
        try:
            y, m, d = (int(x) for x in date_str.split("-")[:3])
        except (ValueError, IndexError):
            y = m = d = None
    if y is None and fallback_dt is not None:
        y, m, d = fallback_dt.year, fallback_dt.month, fallback_dt.day
    if y is None:
        return None
    minutes %= 24 * 60
    return datetime(y, m, d, minutes // 60, minutes % 60, tzinfo=tzinfo).isoformat()


def _travel_info_from_dict(d: dict) -> TravelInfo:
    return TravelInfo(
        distance_meters=d.get("distance_meters"),
        duration_minutes=d.get("duration_minutes"),
        transport_mode=d.get("transport_mode", "car"),
        route_summary=d.get("route_summary"),
        source=d.get("source", "naver_maps"),
        note=d.get("note"),
    )


def _resolve_travel(sch, profile: UserProfile, mode: str) -> Optional[dict]:
    """Best-effort travel from user's current location to the schedule place."""
    cur = profile.current_location
    if not cur or cur.latitude is None or cur.longitude is None:
        return None
    d_lat, d_lng = sch.latitude, sch.longitude
    if d_lat is None or d_lng is None:
        if sch.location:
            try:
                geo = maps.geocode(sch.location)
            except Exception:
                geo = None
            if geo:
                d_lat, d_lng = geo["latitude"], geo["longitude"]
    if d_lat is None or d_lng is None:
        return None
    return travel_svc.safe_compute_travel(cur.latitude, cur.longitude, d_lat, d_lng, mode)


def build_departure_plan_with_travel(req: DeparturePlanRequest) -> DepartureAlertPlanData:
    """Travel-aware planner.

    departure_time = start - travel_minutes - departure_buffer_minutes
    trigger        = departure_time - 10 minutes
    Falls back to start - default_alert_minutes_before when travel is unavailable.
    """
    sch = req.schedule
    profile = req.user_profile or UserProfile()
    opts = req.options or AlertOptions()
    mode = (profile.transport_mode or "car")

    tzinfo = _tzinfo_from(req.current_datetime)
    fallback_dt = _fallback_date(req.current_datetime)

    travel = _resolve_travel(sch, profile, mode) if opts.include_travel_time else None
    travel_min = travel.get("duration_minutes") if travel else None
    buffer = max(0, profile.departure_buffer_minutes)

    reminders: List[TravelAwareReminder] = []
    voice_text: Optional[str] = None
    start_min = _to_min(sch.start_time)

    if start_min is not None:
        if travel_min is not None:
            dep_min = max(0, start_min - travel_min - buffer)
        else:
            dep_min = max(0, start_min - max(0, profile.default_alert_minutes_before))
        departure_time = _to_hhmm(dep_min)
        trigger_min = max(0, dep_min - 10)
        trigger_dt = _iso_at(sch.date, trigger_min, tzinfo, fallback_dt)

        dh, dm = dep_min // 60, dep_min % 60
        if travel_min is not None:
            message = (
                f"목적지까지 약 {travel_min}분 걸려요. 여유 시간을 고려하면 "
                f"{dh}시 {dm:02d}분쯤 출발하는 걸 추천해요."
            )
            voice_text = (
                f"목적지까지 약 {travel_min}분 걸려요. 늦지 않으려면 "
                f"{dh}시 {dm:02d}분쯤 출발하는 걸 추천해요."
            )
        else:
            message = f"{departure_time}에 출발하면 {sch.title} 시간에 맞출 수 있어요."
            voice_text = message

        if opts.include_departure_alert:
            reminders.append(
                TravelAwareReminder(
                    reminder_id=f"rem_departure_{sch.id or '001'}",
                    type="departure",
                    trigger_datetime=trigger_dt,
                    departure_time=departure_time,
                    title="출발 준비 알림",
                    message=message,
                    notification_channel="local_push",
                )
            )

    plan = AlertPlan(
        travel=_travel_info_from_dict(travel) if travel else None,
        reminders=reminders,
        voice_alert_text=voice_text if opts.voice_enabled else None,
        save_required_on_frontend=True,
    )
    return DepartureAlertPlanData(schedule_id=sch.id, alert_plan=plan)
