"""On-device VLM adapters."""

from .base import ModelNotAvailable, VLMAdapter, empty_vision_analysis
from .minicpm_v_adapter import MiniCPMVAdapter
from .mobilevlm_adapter import MobileVLMAdapter
from .mock_adapter import MockAdapter
from .qwen_awq_adapter import QwenAWQAdapter
from .smolvlm_adapter import SmolVLMAdapter

# model_candidates.yaml 의 adapter 키 → 어댑터 클래스
ADAPTER_REGISTRY: dict[str, type[VLMAdapter]] = {
    "minicpm_v": MiniCPMVAdapter,
    "mobilevlm": MobileVLMAdapter,
    "smolvlm": SmolVLMAdapter,
    "qwen_awq": QwenAWQAdapter,
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
    "MiniCPMVAdapter", "MobileVLMAdapter", "SmolVLMAdapter", "QwenAWQAdapter", "MockAdapter",
    "ADAPTER_REGISTRY", "build_adapter",
]
