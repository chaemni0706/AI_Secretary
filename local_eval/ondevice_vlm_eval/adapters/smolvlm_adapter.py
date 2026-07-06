"""SmolVLM adapter (stub).

SmolVLM-500M / SmolVLM-2.2B (초경량 VLM, Idefics3 계열) 어댑터 자리.
실제 통합 예정 경로: ONNX Runtime / llama.cpp / MLC-LLM. 아직 가중치/런타임 미탑재.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter


class SmolVLMAdapter(VLMAdapter):
    ADAPTER_KEY = "smolvlm"

    def available(self) -> bool:
        return False

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        raise ModelNotAvailable(
            "SmolVLM is not wired yet. Run the on-device eval with --simulate to use manifest fixtures."
        )
