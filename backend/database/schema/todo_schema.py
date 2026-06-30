"""To-do (TODO) request/response schemas.

Maps onto planner_items + todo_details. `completed` is derived from the
planner status (COMPLETED) rather than stored as a separate boolean column.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.database.schema.local_schedule_schema import ScheduleDraftInput


class TodoCreate(BaseModel):
    title: str
    due_date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    priority: str = "medium"
    completed: bool = False
    category: Optional[str] = None
    memo: Optional[str] = None
    source: str = "user"


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None
    category: Optional[str] = None
    memo: Optional[str] = None
    source: Optional[str] = None


class TodoRead(BaseModel):
    id: str
    title: str
    due_date: Optional[str] = None
    priority: str
    completed: bool
    category: Optional[str] = None
    memo: Optional[str] = None
    status: str
    source: str
    created_at: str
    updated_at: str


class TodoFromDraftRequest(BaseModel):
    schedule_draft: ScheduleDraftInput
    intent: Optional[str] = Field(None, description="parse 응답의 intent (예: create_todo)")
