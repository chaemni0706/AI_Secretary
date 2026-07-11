"""Server Fallback VLM 후보 registry.

목적: fallback evidence engine 에 쓸 수 있는 서버 VLM 후보들을 하나의 표로 관리.
각 후보는 동일 interface(ServerVlmEvidenceEngine)로 로드/추론되고, **동일 evidence JSON schema** 를 산출한다.
final_result 는 절대 여기서 결정하지 않는다(기존 Rule Engine 이 판정).

loader:
  - "qwen2_5_vl": transformers Qwen2_5_VLForConditionalGeneration + AutoProcessor (+ qwen_vl_utils)
  - "auto_trust": AutoModelForCausalLM + AutoProcessor, trust_remote_code=True (A.X 등 커스텀 아키텍처)

주의: weight 는 git 미포함. 존재하지 않는 경로/미다운로드 후보는 available=False 로 표시(엔진이 engine_error 처리).
"""
from __future__ import annotations

import os
from pathlib import Path

REGISTRY = {
    # 현 incumbent fallback. non-AWQ bf16(AWQ 는 Triton generate 실패 이력).
    "qwen25_3b": {
        "display": "Qwen2.5-VL-3B-Instruct (bf16)",
        "model_path": "/data/models/Qwen2.5-VL-3B-Instruct",
        "loader": "qwen2_5_vl",
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "note": "현 fallback baseline. mini_probe48 FP=14(water=12).",
    },
    # 로컬 존재 후보(SKT). 커스텀 아키텍처 a.x-4-vl → trust_remote_code.
    "ax_4_0_vl_light": {
        "display": "SKT A.X-4.0-VL-Light",
        "model_path": "/data/models/A.X-4.0-VL-Light",
        "loader": "auto_trust",
        "dtype": "bfloat16",
        "trust_remote_code": True,
        "note": "text backbone qwen2, vision tower 포함. ~15G.",
    },
    # 채택된 fallback(bf16 다운로드 완료). end-to-end 기본값.
    "qwen25_7b": {
        "display": "Qwen2.5-VL-7B-Instruct (bf16)",
        "model_path": "/data/models/Qwen2.5-VL-7B-Instruct",
        "loader": "qwen2_5_vl",
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "note": "선택된 fallback(2026-07-11). bf16 16G 다운로드 완료. AWQ 금지(Triton). Gate C FP=6.",
    },
    "qwen3_8b": {
        "display": "Qwen3-VL-8B-Instruct",
        "model_path": "/data/models/Qwen3-VL-8B-Instruct",
        "loader": "qwen3_vl",
        "dtype": "bfloat16",
        "trust_remote_code": False,
        "note": "미다운로드(~18G).",
    },
}


def get(model_key: str) -> dict:
    if model_key not in REGISTRY:
        raise KeyError(f"unknown model_key={model_key}; known={list(REGISTRY)}")
    spec = dict(REGISTRY[model_key])
    spec["key"] = model_key
    # env override for model path (e.g. SERVER_VLM_PATH_ax_4_0_vl_light)
    env_path = os.environ.get(f"SERVER_VLM_PATH_{model_key}")
    if env_path:
        spec["model_path"] = env_path
    spec["available"] = Path(spec["model_path"]).exists()
    return spec


def available_keys() -> list:
    return [k for k in REGISTRY if Path(get(k)["model_path"]).exists()]


if __name__ == "__main__":
    import json
    rows = {k: {"display": get(k)["display"], "available": get(k)["available"],
                "path": get(k)["model_path"]} for k in REGISTRY}
    print(json.dumps(rows, ensure_ascii=False, indent=2))
