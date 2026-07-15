"""로컬 온디바이스 VLM analyzer — backend verification pipeline 용 thin wrapper.

목적: OpenAI 키 없이 로컬 소형 VLM(SmolVLM-500M, Qwen2.5-VL-3B-AWQ 등)으로 이미지 인증을
동작시킨다. 실험 코드(local_eval/ondevice_vlm_eval/adapters)의 어댑터를 그대로 재사용하고,
그 출력(정규화 dict)을 backend 의 VisionAnalysis(pydantic) 로 감싼다.

원칙(기존 구조 유지):
- 모델은 PASS/FAIL 을 결정하지 않는다. 관찰된 시각 evidence(VisionAnalysis) 만 만든다.
- 최종 verified/rejected/retake_required 는 항상 Rule Engine(evaluate_image_verification)이 결정한다.
- 어댑터/가중치가 없으면 available()=False → 상위(service)에서 안전하게 처리.

provider key 는 local_eval 의 ADAPTER_REGISTRY 키(smolvlm / qwen_awq / mobilevlm / smolvlm2_2b / mock)와
동일하며, model_candidates.yaml 의 메타(model_id/model_path/max_new_tokens)를 로딩에 사용한다.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Iterable, Optional

from backend.database.schema.image_verification_schema import (
    ImageQuality,
    VerificationType,
    VisionAnalysis,
)
from backend.services.vision_analyzer import VisionAnalyzer, _unavailable_analysis

# local_eval 실험 어댑터를 import 경로에 추가 (metrics 저장 구조 등은 건드리지 않고 어댑터만 재사용).
_ONDEVICE_DIR = (
    Path(__file__).resolve().parents[2] / "local_eval" / "ondevice_vlm_eval"
)
if str(_ONDEVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_ONDEVICE_DIR))

_CANDIDATES_YAML = _ONDEVICE_DIR / "model_candidates.yaml"


def _load_candidate_meta(provider_key: str) -> dict:
    """model_candidates.yaml 에서 adapter==provider_key 인 후보 메타를 찾는다(없으면 {})."""
    try:
        import yaml

        data = yaml.safe_load(_CANDIDATES_YAML.read_text(encoding="utf-8")) or {}
        for cand in data.get("candidates", []):
            if cand.get("adapter") == provider_key:
                return dict(cand)
    except Exception:  # noqa: BLE001 - 메타 없음/파싱 실패는 기본값으로 진행
        pass
    return {}


class LocalVLMVisionAnalyzer(VisionAnalyzer):
    """local_eval 온디바이스 어댑터 하나를 VisionAnalyzer 로 감싸는 wrapper.

    가중치는 어댑터 __init__ 에서 1회 로드된다(무겁다). 프로세스당 provider 별 singleton 으로
    재사용하는 것을 권장 → get_local_vlm_analyzer() 사용.
    """

    def __init__(self, provider_key: str, meta: Optional[dict] = None):
        self.provider_key = provider_key
        from adapters import build_adapter  # local_eval ondevice 어댑터 레지스트리

        resolved_meta = _load_candidate_meta(provider_key)
        if meta:
            resolved_meta.update(meta)
        self._adapter = build_adapter(provider_key, meta=resolved_meta)

    def available(self) -> bool:
        try:
            return bool(self._adapter.available())
        except Exception:  # noqa: BLE001
            return False

    @property
    def model_load_time_ms(self) -> float:
        return float(getattr(self._adapter, "model_load_time_ms", 0.0) or 0.0)

    def analyze(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
    ) -> VisionAnalysis:
        return self.analyze_with_context(image_path, verification_type, allowed_labels)

    def analyze_with_context(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
        exercise_activity_type: str | None = None,
    ) -> VisionAnalysis:
        """activity 를 어댑터 context 로 전달하는 버전.

        exercise 정규화기는 activity 를 알아야 gym_environment / home_workout_environment 를
        보강한다(예: home workout 자세 → home_workout_environment + home_exercise_pose_visible).
        activity 가 None 이면 그 보강이 비활성화되므로, 서비스가 인증 요청의 activity 를 넘긴다.
        """
        if not self.available():
            return _unavailable_analysis(
                f"Local VLM '{self.provider_key}' is not loaded."
            )
        try:
            ctx = {
                "verification_type": verification_type,
                "exercise_activity_type": exercise_activity_type,
            }
            normalized = self._adapter.analyze(Path(image_path), verification_type, ctx)
        except Exception as exc:  # noqa: BLE001 - provider 오류는 unusable 로 흡수(에러 누수 방지)
            return _unavailable_analysis(f"Local VLM analysis failed: {type(exc).__name__}")
        analysis = _dict_to_vision_analysis(normalized, allowed_labels)
        # 진단 로그: 모델 raw_output → 정규화 evidence 생성 과정 확인용(파서/프롬프트 문제 추적).
        _log_vlm_debug(self.provider_key, verification_type, normalized, analysis)
        return analysis


def _log_vlm_debug(provider, verification_type, normalized, analysis) -> None:
    ev_field = f"{verification_type}_visual_evidence"
    raw = normalized.get("_raw_text") if isinstance(normalized, dict) else None
    norm_ev = normalized.get(ev_field) if isinstance(normalized, dict) else None
    print("---------- LOCAL VLM ANALYZE ----------")
    print(f"[vlm] provider={provider} type={verification_type}")
    print(f"[vlm] raw_output={raw!r}")
    print(f"[vlm] normalized.{ev_field}={norm_ev}")
    print(f"[vlm] objects={[o.get('label') for o in (normalized.get('objects') or [])]}")
    print(f"[vlm] final {ev_field}={getattr(analysis, ev_field, None)} usable={analysis.quality.usable}")
    print("---------------------------------------")


def _dict_to_vision_analysis(
    normalized: dict, allowed_labels: Iterable[str]
) -> VisionAnalysis:
    """어댑터의 정규화 dict → VisionAnalysis. object 는 allowed_labels 로 필터(OpenAI analyzer 와 동일)."""
    if not isinstance(normalized, dict):
        return _unavailable_analysis("Local VLM returned no analysis.")
    allowed = set(allowed_labels)
    payload = dict(normalized)
    payload.pop("_raw_text", None)  # 내부 디버그 필드는 스키마에 없음
    payload["objects"] = [
        o for o in payload.get("objects", []) if isinstance(o, dict) and o.get("label") in allowed
    ]
    quality = payload.get("quality")
    if isinstance(quality, dict):
        payload["quality"] = ImageQuality(**quality)
    try:
        return VisionAnalysis(**payload)
    except Exception:  # noqa: BLE001 - 스키마 불일치는 unusable 로 흡수
        return _unavailable_analysis("Local VLM output could not be parsed.")


# ---------------------------------------------------------------------------
# provider 별 singleton (가중치 재로딩 방지)
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()
_INSTANCES: dict[str, LocalVLMVisionAnalyzer] = {}


def get_local_vlm_analyzer(provider_key: str) -> LocalVLMVisionAnalyzer:
    """provider_key 별로 캐시된 LocalVLMVisionAnalyzer 반환(최초 1회 모델 로드)."""
    with _LOCK:
        inst = _INSTANCES.get(provider_key)
        if inst is None:
            inst = LocalVLMVisionAnalyzer(provider_key)
            _INSTANCES[provider_key] = inst
        return inst
