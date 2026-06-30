"""Notification plan from a stored Schedule + user preferences.

Reuses departure_alert.build_departure_plan unchanged. Resolves travel/buffer/
preference by priority (request > memory > departure_alert default), computes a
plan, and can optionally persist it to the reminders table. No push delivery.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.alert_schema import (
    AlertContext,
    AlertSchedule,
    DeparturePlanRequest,
    UserPreference,
)
from backend.database.schema.notification_schema import (
    NotificationPlanData,
    NotificationPlanRequest,
)
from backend.services import local_schedule_service as schedule_service
from backend.services import memory_service
from backend.services.departure_alert import build_departure_plan


def build_plan(db: Session, req: NotificationPlanRequest) -> Optional[NotificationPlanData]:
    """Return a notification plan for a stored schedule, or None if not found."""
    sched = schedule_service.get_schedule(db, req.schedule_id)
    if sched is None:
        return None

    # --- resolve settings: request > memory > departure_alert default --------
    mem_ctx = memory_service.get_user_context(db, req.user_id) if req.user_id else None

    if req.travel_minutes is not None:
        travel = req.travel_minutes
    elif mem_ctx is not None:
        travel = mem_ctx["default_travel_minutes"]
    else:
        travel = 0  # departure_alert default (AlertContext.estimated_travel_minutes)

    if req.buffer_minutes is not None:
        buffer = req.buffer_minutes
    elif mem_ctx is not None:
        buffer = mem_ctx["default_buffer_minutes"]
    else:
        buffer = 0

    if req.notification_preference is not None:
        if req.notification_preference not in memory_service.NOTIF_VALUES:
            raise ValueError(
                f"notification_preference는 {sorted(memory_service.NOTIF_VALUES)} 중 하나여야 합니다."
            )
        preference = req.notification_preference
    elif mem_ctx is not None:
        preference = mem_ctx["notification_preference"]
    else:
        preference = "normal"
    pref_fields = memory_service.to_alert_preference(preference)

    # --- reuse departure_alert logic (no change to that module) --------------
    alert_req = DeparturePlanRequest(
        schedule=AlertSchedule(
            title=sched.title,
            category=(sched.category or "etc"),
            date=sched.date,
            start_time=sched.start_time or "",   # invalid/empty -> safe partial plan
            location=sched.location,
        ),
        context=AlertContext(
            weather=req.weather,
            estimated_travel_minutes=max(0, travel),
            buffer_minutes=max(0, buffer),
        ),
        user_preference=UserPreference(**pref_fields),
    )
    plan = build_departure_plan(alert_req)

    checklist = plan.checklist if req.include_checklist else []

    # --- optional persistence to reminders -----------------------------------
    persisted = 0
    if req.persist and sched.date and plan.leave_time and plan.notifications:
        rows = [
            {
                "reminder_type": "DEPARTURE" if n.time == plan.leave_time else "PREPARATION",
                "trigger_at": f"{sched.date}T{n.time}:00",
                "message_text": n.message,
            }
            for n in plan.notifications
        ]
        persisted = repo.replace_reminders_for_item(db, item_id=req.schedule_id, reminders=rows)
        db.commit()

    return NotificationPlanData(
        schedule_id=req.schedule_id,
        user_id=req.user_id,
        leave_time=plan.leave_time,
        checklist=checklist,
        notifications=plan.notifications,
        source="stored_schedule",
        applied_preference=preference,
        applied_travel_minutes=plan.estimated_travel_minutes,
        applied_buffer_minutes=plan.buffer_minutes,
        persisted_reminders=persisted,
    )
