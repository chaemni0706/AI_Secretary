"""Qwen2.5-VL-3B-AWQ adapter (stub).

Qwen2.5-VL-3B의 AWQ 4bit 양자화 버전 어댑터 자리 (온디바이스 후보 + 기존 파이프라인과의 비교 기준).
실제 통합 예정 경로: MLC-LLM(on-device) / vLLM(server). 아직 가중치/런타임 미탑재.

참고: 비양자화 Qwen2.5-VL-3B 실행은 기존 local_eval/qwen_vlm_eval/scripts/run_qwen_single.py에 있다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter


class QwenAWQAdapter(VLMAdapter):
    ADAPTER_KEY = "qwen_awq"

    def available(self) -> bool:
        return False

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        raise ModelNotAvailable(
            "Qwen2.5-VL-3B-AWQ is not wired yet. Run the on-device eval with --simulate to use manifest fixtures."
        )
