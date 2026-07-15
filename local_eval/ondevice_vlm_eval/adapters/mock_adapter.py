"""Mock adapter — 실제 모델 없이 러너/리포트 구조를 검증하기 위한 어댑터.

주입된 fixture_lookup(image_path/filename) -> VisionAnalysis 호환 dict 를 그대로 반환한다.
(매니페스트에 사람이 검수해 넣은 vision_analysis 픽스처 = '완벽한 모델' 시뮬레이션)

실제 후보 모델이 아직 준비되지 않았을 때, 러너는 이 어댑터로 대체해 파이프라인을 end-to-end로 돌린다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from .base import VLMAdapter, empty_vision_analysis


class MockAdapter(VLMAdapter):
    def __init__(self, fixture_lookup: Callable[[str], Optional[dict]], meta: Optional[dict[str, Any]] = None):
        super().__init__(meta)
        self._lookup = fixture_lookup

    def available(self) -> bool:
        return True

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        key = Path(image_path).name
        fixture = self._lookup(key)
        if fixture is None:
            return empty_vision_analysis()
        # 방어적 복사 (러너가 여러 모델에 재사용해도 오염되지 않도록)
        return dict(fixture)
