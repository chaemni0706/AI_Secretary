"""Shared schema building blocks.

Conventions (shared with the Flutter frontend):
- Date  -> string "YYYY-MM-DD"
- Time  -> string "HH:mm"
- All API responses use the envelope: success / message / data
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Source(str, Enum):
    ai = "ai"
    user = "user"
    voice = "voice"  # 음성 입력으로 생성된 초안 (input_type="voice")


class InputType(str, Enum):
    text = "text"
    voice = "voice"


class BaseResponse(BaseModel, Generic[T]):
    """Common response envelope. Concrete responses set the `data` type."""

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None
