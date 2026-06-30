"""Dashboard (calendar + to-do) read schemas.

Aggregated views over the existing local Schedule/To-do stores. No new tables;
reuses ScheduleRead / TodoRead.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from backend.database.schema.local_schedule_schema import ScheduleRead
from backend.database.schema.todo_schema import TodoRead


class HighPriorityItem(BaseModel):
    type: str = Field(..., description="'schedule' | 'todo'")
    id: str
    title: str
    priority: str
    when: Optional[str] = Field(None, description="schedule=date / todo=due_date")


class DashboardTodayData(BaseModel):
    date: str
    schedules: List[ScheduleRead] = Field(default_factory=list)
    todos: List[TodoRead] = Field(default_factory=list)
    next_schedule: Optional[ScheduleRead] = None
    total_schedule_count: int = 0
    total_todo_count: int = 0
    completed_todo_count: int = 0
    todo_completion_rate: float = 0.0
    high_priority_items: List[HighPriorityItem] = Field(default_factory=list)
    summary_message: str = ""


class DashboardSummaryData(BaseModel):
    date: str
    total_schedule_count: int = 0
    total_todo_count: int = 0
    completed_todo_count: int = 0
    todo_completion_rate: float = 0.0
    high_priority_items: List[HighPriorityItem] = Field(default_factory=list)
    next_schedule: Optional[ScheduleRead] = None
    summary_message: str = ""
