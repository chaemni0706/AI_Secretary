"""Dashboard aggregation service.

Reuses the local Schedule/To-do services (and thus the planner_items store);
no separate mock source. Date filtering + sorting + aggregates only.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.dashboard_schema import (
    DashboardStats,
    DashboardSummaryData,
    DashboardTodayData,
    HighPriorityItem,
)
from backend.database.schema.local_schedule_schema import ScheduleRead
from backend.database.schema.todo_schema import TodoRead
from backend.services import local_schedule_service as sched_service
from backend.services import todo_service as todo_service

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _now_parts(current_datetime: Optional[str]) -> Tuple[str, str]:
    """Return (now_date 'YYYY-MM-DD', now_minute 'YYYY-MM-DDTHH:MM').

    Uses caller-supplied current_datetime when given (deterministic / testable),
    else the server clock.
    """
    if current_datetime and "T" in current_datetime and len(current_datetime) >= 16:
        return current_datetime[:10], current_datetime[:16]
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%dT%H:%M")


def _collect(db: Session, user_id: str, date: str) -> Tuple[List[ScheduleRead], List[TodoRead]]:
    schedules = [s for s in sched_service.list_schedules(db, user_id=user_id) if s.date == date]
    schedules.sort(key=lambda s: s.start_time or "")  # start_time asc
    todos = [t for t in todo_service.list_todos(db, user_id=user_id) if t.due_date == date]
    todos.sort(key=lambda t: (
        t.completed,                              # not-completed first
        _PRIORITY_RANK.get(t.priority, 1),        # high > medium > low
        t.due_date or "9999-99-99",               # earliest due first
    ))
    return schedules, todos


def _next_schedule(schedules: List[ScheduleRead], now_minute: str) -> Optional[ScheduleRead]:
    """Earliest schedule at/after `now` (schedules already start_time-sorted)."""
    for s in schedules:
        if not s.start_time:
            continue
        if f"{s.date}T{s.start_time}" >= now_minute:
            return s
    return None


def _high_priority(schedules, todos) -> List[HighPriorityItem]:
    items: List[HighPriorityItem] = []
    for s in schedules:
        if s.priority == "high":
            items.append(HighPriorityItem(type="schedule", id=s.id, title=s.title,
                                          priority="high", when=s.date))
    for t in todos:
        if t.priority == "high":
            items.append(HighPriorityItem(type="todo", id=t.id, title=t.title,
                                          priority="high", when=t.due_date))
    return items


def _summary_message(date, n_sched, n_todo, n_done, rate, nxt) -> str:
    if n_sched == 0 and n_todo == 0:
        return f"{date}에는 일정과 할 일이 없습니다."
    msg = f"{date} 기준 일정 {n_sched}건, 할 일 {n_todo}건"
    if n_todo:
        msg += f" (완료 {n_done}건, {int(round(rate * 100))}%)"
    msg += "."
    if nxt:
        msg += f" 다음 일정: {nxt.start_time} {nxt.title}."
    return msg


def _aggregate(schedules, todos, now_minute, date):
    n_sched = len(schedules)
    n_todo = len(todos)
    n_done = sum(1 for t in todos if t.completed)
    rate = round(n_done / n_todo, 2) if n_todo else 0.0
    nxt = _next_schedule(schedules, now_minute)
    high = _high_priority(schedules, todos)
    msg = _summary_message(date, n_sched, n_todo, n_done, rate, nxt)
    return n_sched, n_todo, n_done, rate, nxt, high, msg


def get_today(
    db: Session, *, date: Optional[str] = None,
    current_datetime: Optional[str] = None, user_id: Optional[str] = None,
) -> DashboardTodayData:
    user_id = user_id or repo.DEFAULT_USER_ID
    now_date, now_minute = _now_parts(current_datetime)
    date = date or now_date
    schedules, todos = _collect(db, user_id, date)
    n_sched, n_todo, n_done, rate, nxt, high, msg = _aggregate(schedules, todos, now_minute, date)
    return DashboardTodayData(
        date=date, schedules=schedules, todos=todos, next_schedule=nxt,
        total_schedule_count=n_sched, total_todo_count=n_todo,
        completed_todo_count=n_done, todo_completion_rate=rate,
        stats=DashboardStats(
            schedule_count=n_sched, todo_count=n_todo,
            completed_todo_count=n_done, todo_completion_rate=rate,
        ),
        high_priority_items=high, summary_message=msg,
    )


def get_summary(
    db: Session, *, date: Optional[str] = None,
    current_datetime: Optional[str] = None, user_id: Optional[str] = None,
) -> DashboardSummaryData:
    user_id = user_id or repo.DEFAULT_USER_ID
    now_date, now_minute = _now_parts(current_datetime)
    date = date or now_date
    schedules, todos = _collect(db, user_id, date)
    n_sched, n_todo, n_done, rate, nxt, high, msg = _aggregate(schedules, todos, now_minute, date)
    return DashboardSummaryData(
        date=date, total_schedule_count=n_sched, total_todo_count=n_todo,
        completed_todo_count=n_done, todo_completion_rate=rate,
        stats=DashboardStats(
            schedule_count=n_sched, todo_count=n_todo,
            completed_todo_count=n_done, todo_completion_rate=rate,
        ),
        high_priority_items=high, next_schedule=nxt, summary_message=msg,
    )
