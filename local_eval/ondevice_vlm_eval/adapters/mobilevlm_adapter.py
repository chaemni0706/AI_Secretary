"""MobileVLM V2 adapter (stub).

MobileVLM V2 1.7B (모바일 특화 경량 VLM) 어댑터 자리.
실제 통합 예정 경로: llama.cpp / MLC-LLM / NNAPI. 아직 가중치/런타임 미탑재.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter


class MobileVLMAdapter(VLMAdapter):
    ADAPTER_KEY = "mobilevlm"

    def available(self) -> bool:
        return False

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        raise ModelNotAvailable(
            "MobileVLM V2 is not wired yet. Run the on-device eval with --simulate to use manifest fixtures."
        )
