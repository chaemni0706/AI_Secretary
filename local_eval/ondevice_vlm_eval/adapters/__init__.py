"""On-device VLM adapters."""

from .base import ModelNotAvailable, VLMAdapter, empty_vision_analysis
from .magicvl_adapter import MagicVLAdapter
from .minicpm_v_adapter import MiniCPMV2Adapter, MiniCPMVAdapter
from .mobilevlm_adapter import MobileVLMAdapter
from .mock_adapter import MockAdapter
from .qwen_awq_adapter import Qwen2VL2BAdapter, QwenAWQAdapter
from .smolvlm_adapter import SmolVLM2Adapter, SmolVLMAdapter

# model_candidates.yaml 의 adapter 키 → 어댑터 클래스
ADAPTER_REGISTRY: dict[str, type[VLMAdapter]] = {
    "minicpm_v": MiniCPMVAdapter,
    "minicpm_v2": MiniCPMV2Adapter,
    "mobilevlm": MobileVLMAdapter,
    "smolvlm": SmolVLMAdapter,
    "smolvlm2_2b": SmolVLM2Adapter,
    "qwen_awq": QwenAWQAdapter,
    "qwen2vl_2b": Qwen2VL2BAdapter,
    "magicvl_2b": MagicVLAdapter,
    "mock": MockAdapter,
}


def build_adapter(adapter_key: str, meta: dict | None = None, fixture_lookup=None) -> VLMAdapter:
    """adapter 키로 어댑터 인스턴스 생성. mock은 fixture_lookup이 필요하다."""
    if adapter_key not in ADAPTER_REGISTRY:
        raise KeyError(f"unknown adapter: {adapter_key}")
    cls = ADAPTER_REGISTRY[adapter_key]
    if cls is MockAdapter:
        if fixture_lookup is None:
            raise ValueError("MockAdapter requires fixture_lookup")
        return MockAdapter(fixture_lookup, meta=meta)
    return cls(meta=meta)


__all__ = [
    "VLMAdapter", "ModelNotAvailable", "empty_vision_analysis",
    "MiniCPMVAdapter", "MiniCPMV2Adapter", "MobileVLMAdapter", "SmolVLMAdapter", "SmolVLM2Adapter",
    "QwenAWQAdapter", "Qwen2VL2BAdapter", "MagicVLAdapter", "MockAdapter",
    "ADAPTER_REGISTRY", "build_adapter",
]
