"""To-do (TODO) request/response schemas.

Maps onto planner_items + todo_details. `completed` is derived from the
planner status (COMPLETED) rather than stored as a separate boolean column.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.local_schedule_schema import ScheduleDraftInput


class TodoCreate(BaseModel):
    title: str
    due_date: Optional[str] = Field(None, description="'YYYY-MM-DD' (마감일)")
    due_time: Optional[str] = Field(None, description="'HH:mm' (마감 시각, 선택)")
    start_date: Optional[str] = Field(None, description="'YYYY-MM-DD' (시작일, 선택)")
    start_time: Optional[str] = Field(None, description="'HH:mm' (시작 시각, 선택)")
    priority: str = "medium"
    completed: bool = False
    category: Optional[str] = None
    memo: Optional[str] = None
    source: str = "user"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "자료 정리하기",
                "due_date": "2026-07-03",
                "priority": "medium",
                "completed": False,
                "category": "study",
                "source": "user",
            }
        }
    )


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    start_date: Optional[str] = None
    start_time: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None
    category: Optional[str] = None
    memo: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={"example": {"completed": True}}
    )


class TodoRead(BaseModel):
    id: str
    title: str
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    start_date: Optional[str] = None
    start_time: Optional[str] = None
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule_draft": {
                    "title": "장보기",
                    "category": "etc",
                    "date": "2026-07-03",
                    "priority": "medium",
                    "source": "ai",
                },
                "intent": "create_todo",
            }
        }
    )
