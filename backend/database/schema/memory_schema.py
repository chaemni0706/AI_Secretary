"""Personal memory / user-preference schemas (rule-based, no LLM/RAG).

Backed by the existing user_memories table (memory_type PREFERENCE / PLACE).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PlaceItem(BaseModel):
    name: str
    address: Optional[str] = None
    category: Optional[str] = None


class MemoryData(BaseModel):
    user_id: str
    notification_preference: str = "normal"  # normal | strong | forgetful | late_prone
    default_travel_minutes: int = 30
    default_buffer_minutes: int = 10
    preferred_transport: str = "public_transport"  # walk | car | public_transport
    home_location: Optional[str] = None
    work_or_school_location: Optional[str] = None
    frequently_visited_places: List[PlaceItem] = Field(default_factory=list)
    checklist_preferences: List[str] = Field(default_factory=list)
    updated_at: Optional[str] = None


class MemoryUpsert(BaseModel):
    """PUT body — provided fields are written (upsert)."""
    notification_preference: Optional[str] = None
    default_travel_minutes: Optional[int] = None
    default_buffer_minutes: Optional[int] = None
    preferred_transport: Optional[str] = None
    home_location: Optional[str] = None
    work_or_school_location: Optional[str] = None
    frequently_visited_places: Optional[List[PlaceItem]] = None
    checklist_preferences: Optional[List[str]] = None


class PreferencesPatch(BaseModel):
    notification_preference: Optional[str] = None
    default_travel_minutes: Optional[int] = None
    default_buffer_minutes: Optional[int] = None
    preferred_transport: Optional[str] = None
    checklist_preferences: Optional[List[str]] = None


class PlaceCreate(BaseModel):
    name: str
    address: Optional[str] = None
    category: Optional[str] = None
