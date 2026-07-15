"""SQLAlchemy ORM models mirroring ``database/local_schema.sql`` 1:1.

Rules honored here:
- No new tables are introduced. Each model maps an *existing* table.
- The local schema models EVENTs and TODOs as a single ``planner_items`` table
  (``item_type`` IN ('EVENT','TODO')) plus 1:1 detail tables ``event_details`` /
  ``todo_details``. There are intentionally NO ``schedules`` / ``todos`` tables.
- Enum-like columns use the schema's UPPERCASE CHECK values (see *_VALUES tuples).
  The API/Pydantic layer uses lowercase values, so a mapping layer (next stage)
  must translate; these models stay faithful to the SQL.
- Tables are created from local_schema.sql (see ``init_db``), not via
  ``metadata.create_all``, so triggers and CHECK constraints are preserved.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# --- Allowed CHECK values (UPPERCASE, matching local_schema.sql) -------------
ITEM_TYPE_VALUES = ("EVENT", "TODO")
STATUS_VALUES = ("DRAFT", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
PRIORITY_VALUES = ("HIGH", "MEDIUM", "LOW")
SOURCE_TYPE_VALUES = ("MANUAL", "AI", "EXTERNAL_SYNC")
REMINDER_TYPE_VALUES = ("STANDARD", "PREPARATION", "DEPARTURE", "WEATHER_CONTEXT")
REMINDER_STATUS_VALUES = ("SCHEDULED", "SENT", "CANCELLED", "FAILED")
MEMORY_TYPE_VALUES = ("PREFERENCE", "PERSONA", "PLACE", "PREPARATION", "PATTERN", "FACT")


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    display_name = Column(String)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    timezone = Column(String, nullable=False, default="Asia/Seoul")
    locale = Column(String, nullable=False, default="ko-KR")
    default_reminder_minutes = Column(Integer)
    preferred_briefing_time = Column(String)
    notification_persona = Column(String)
    memory_enabled = Column(Integer, nullable=False, default=1)
    emotion_coaching_enabled = Column(Integer, nullable=False, default=0)
    sensitive_data_consent = Column(Integer, nullable=False, default=0)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class Calendar(Base):
    __tablename__ = "calendars"

    calendar_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    is_primary = Column(Integer, nullable=False, default=0)
    is_visible = Column(Integer, nullable=False, default=1)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class PlannerItem(Base):
    __tablename__ = "planner_items"

    item_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)
    status = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="MEDIUM")
    source_type = Column(String, nullable=False, default="MANUAL")
    sort_at = Column(String)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    deleted_at = Column(String)

    __table_args__ = (
        CheckConstraint("item_type IN ('EVENT','TODO')", name="ck_planner_item_type"),
    )

    event_detail = relationship(
        "EventDetail", back_populates="planner_item", uselist=False
    )
    todo_detail = relationship(
        "TodoDetail", back_populates="planner_item", uselist=False
    )
    reminders = relationship("Reminder", back_populates="planner_item")


class EventDetail(Base):
    __tablename__ = "event_details"

    item_id = Column(String, ForeignKey("planner_items.item_id", ondelete="CASCADE"), primary_key=True)
    calendar_id = Column(String, ForeignKey("calendars.calendar_id", ondelete="RESTRICT"), nullable=False)
    start_at = Column(String, nullable=False)
    end_at = Column(String)
    is_all_day = Column(Integer, nullable=False, default=0)
    location_text = Column(String)
    travel_time_minutes = Column(Integer)
    external_event_id = Column(String)

    planner_item = relationship("PlannerItem", back_populates="event_detail")


class TodoDetail(Base):
    __tablename__ = "todo_details"

    item_id = Column(String, ForeignKey("planner_items.item_id", ondelete="CASCADE"), primary_key=True)
    due_at = Column(String)
    planned_date = Column(String)
    estimated_minutes = Column(Integer)
    started_at = Column(String)
    completed_at = Column(String)

    planner_item = relationship("PlannerItem", back_populates="todo_detail")


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id = Column(String, primary_key=True)
    item_id = Column(String, ForeignKey("planner_items.item_id", ondelete="CASCADE"), nullable=False)
    reminder_type = Column(String, nullable=False)
    trigger_at = Column(String, nullable=False)
    channel = Column(String, nullable=False, default="LOCAL_NOTIFICATION")
    message_text = Column(String)
    context_json = Column(Text)
    status = Column(String, nullable=False, default="SCHEDULED")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    planner_item = relationship("PlannerItem", back_populates="reminders")


class UserMemory(Base):
    __tablename__ = "user_memories"

    memory_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(String, nullable=False)
    memory_key = Column(String, nullable=False)
    memory_value_masked = Column(String, nullable=False)
    tags_json = Column(Text)
    importance = Column(Float)
    confidence = Column(Float)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
