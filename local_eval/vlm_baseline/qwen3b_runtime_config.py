"""Qwen-3B evidence engine runtime config (env-based). 모델 weight 는 repo 에 없음; 경로/옵션만."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _envbool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Qwen3BConfig:
    model_path: str = os.environ.get("QWEN3B_MODEL_PATH", "/data/models/Qwen2.5-VL-3B-Instruct-AWQ")
    device: str = os.environ.get("QWEN3B_DEVICE", "cuda")
    dtype: str = os.environ.get("QWEN3B_DTYPE", "auto")          # auto|bf16|fp16
    max_new_tokens: int = int(os.environ.get("QWEN3B_MAX_NEW_TOKENS", "512"))
    temperature: float = float(os.environ.get("QWEN3B_TEMPERATURE", "0.0"))
    do_sample: bool = _envbool("QWEN3B_DO_SAMPLE", False)

    def torch_dtype(self):
        import torch
        return {"auto": "auto", "bf16": torch.bfloat16, "fp16": torch.float16}.get(self.dtype, "auto")

    def as_dict(self) -> dict:
        return {"model_path": self.model_path, "device": self.device, "dtype": self.dtype,
                "max_new_tokens": self.max_new_tokens, "temperature": self.temperature,
                "do_sample": self.do_sample}


def load_config(model_path: str | None = None) -> Qwen3BConfig:
    cfg = Qwen3BConfig()
    if model_path:
        cfg.model_path = model_path
    return cfg
