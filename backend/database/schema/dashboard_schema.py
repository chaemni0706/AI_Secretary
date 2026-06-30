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


class DashboardStats(BaseModel):
    """Flutter 홈 화면 편의용 집계 묶음.

    상위의 평탄(flat) 카운트 필드와 값이 동일하며, 프론트에서 한 객체로 바로 쓸 수
    있도록 추가로 제공한다(기존 필드는 하위 호환을 위해 유지).
    """

    schedule_count: int = 0
    todo_count: int = 0
    completed_todo_count: int = 0
    todo_completion_rate: float = 0.0


class DashboardTodayData(BaseModel):
    date: str
    schedules: List[ScheduleRead] = Field(default_factory=list)
    todos: List[TodoRead] = Field(default_factory=list)
    next_schedule: Optional[ScheduleRead] = None
    total_schedule_count: int = 0
    total_todo_count: int = 0
    completed_todo_count: int = 0
    todo_completion_rate: float = 0.0
    stats: DashboardStats = Field(default_factory=DashboardStats)
    high_priority_items: List[HighPriorityItem] = Field(default_factory=list)
    summary_message: str = ""


class DashboardSummaryData(BaseModel):
    date: str
    total_schedule_count: int = 0
    total_todo_count: int = 0
    completed_todo_count: int = 0
    todo_completion_rate: float = 0.0
    stats: DashboardStats = Field(default_factory=DashboardStats)
    high_priority_items: List[HighPriorityItem] = Field(default_factory=list)
    next_schedule: Optional[ScheduleRead] = None
    summary_message: str = ""
