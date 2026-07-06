"""MiniCPM-V adapter (stub).

MiniCPM-V 계열(고정밀 소형 VLM)을 온디바이스/서버에서 돌릴 때의 어댑터 자리.
실제 통합 예정 경로: llama.cpp(GGUF int4) 또는 MLC-LLM. 아직 가중치/런타임 미탑재.

실제 구현 시 analyze()는 이미지+타입별 프롬프트로 추론 후, 출력을 VisionAnalysis 호환 dict로
정규화(normalize_water/exercise/study_evidence 재사용 가능)해서 반환한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter


class MiniCPMVAdapter(VLMAdapter):
    ADAPTER_KEY = "minicpm_v"

    def available(self) -> bool:
        # 실제 런타임(transformers/llama.cpp bindings + 가중치)이 붙으면 True로 전환.
        return False

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        raise ModelNotAvailable(
            "MiniCPM-V is not wired yet. Run the on-device eval with --simulate to use manifest fixtures."
        )
