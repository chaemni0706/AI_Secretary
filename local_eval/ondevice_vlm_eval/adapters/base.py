"""On-device VLM adapter 공통 인터페이스.

모든 후보 모델(MiniCPM-V / MobileVLM / SmolVLM / Qwen2.5-VL-AWQ)은 동일한 인터페이스를 따른다:

    analyze(image_path, verification_type, context) -> VisionAnalysis 호환 dict

- 반환 dict는 backend VisionAnalysis 스키마와 호환되어야 한다
  (quality/scene/objects/visible_text/visual_evidence/study_visual_evidence/
   water_visual_evidence/exercise_visual_evidence).
- 실제 모델 로딩/추론은 아직 붙이지 않는다. 실제 adapter는 available()=False,
  analyze()는 ModelNotAvailable을 던진다. 러너는 --simulate 모드에서 매니페스트 픽스처로 대체한다.
- 메타데이터(model_name/model_size_mb/runtime_target 등)는 model_candidates.yaml에서 주입된다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class ModelNotAvailable(RuntimeError):
    """실제 모델 가중치/런타임이 아직 준비되지 않았을 때."""


class VLMAdapter(ABC):
    """온디바이스 VLM 후보 모델 공통 어댑터."""

    def __init__(self, meta: Optional[dict[str, Any]] = None):
        self.meta: dict[str, Any] = dict(meta or {})

    # --- 메타데이터 (model_candidates.yaml에서 주입) ---
    @property
    def model_name(self) -> str:
        return self.meta.get("model_name", self.__class__.__name__)

    @property
    def model_size_mb(self):
        return self.meta.get("model_size_mb", "")

    @property
    def runtime_target(self) -> str:
        return self.meta.get("runtime_target", "")

    def available(self) -> bool:
        """실제 추론이 가능한지. 실제 모델 stub은 아직 False."""
        return False

    @abstractmethod
    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        """이미지에서 관측 근거만 추출해 VisionAnalysis 호환 dict로 반환.

        최종 인증 판정은 하지 않는다(Rule Engine 담당). 실제 모델 미탑재 stub은 ModelNotAvailable.
        """
        raise NotImplementedError


def empty_vision_analysis(usable: bool = True) -> dict:
    """근거가 없을 때 쓰는 최소 VisionAnalysis 호환 dict."""
    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": usable, "issues": []},
        "scene": None,
        "objects": [],
        "visible_text": [],
        "visual_evidence": [],
        "study_visual_evidence": [],
        "water_visual_evidence": [],
        "exercise_visual_evidence": [],
    }
