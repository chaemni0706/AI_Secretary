"""SmolVLM Local Evidence Engine (기존 adapters/smolvlm_adapter 재사용 wrapper).

역할: image_path + task → SmolVLM-500M → VisionAnalysis 호환 evidence dict(기존 스키마 codes). **final_result 미결정.**
기존 코드 재사용: local_eval/ondevice_vlm_eval/adapters.build_adapter("smolvlm") (analyze → VisionAnalysis dict).
모델: /data/models/SmolVLM-500M-Instruct (weight 는 git 미포함). lazy singleton.

주의: SmolVLM 은 final 171 에서 FP=9 이력 → 단독 최종 인증 위험. 여기선 local-first evidence engine 으로만,
불확실/약함은 orchestrator 가 Qwen fallback 으로 넘긴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_OND = _ROOT / "local_eval" / "ondevice_vlm_eval"
for p in (str(_ROOT), str(_OND)):
    if p not in sys.path:
        sys.path.insert(0, p)


class _SmolRuntime:
    _instance = None

    def __init__(self):
        self.adapter = None
        self.load_error = ""

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self):
        if self.adapter is not None:
            return
        from adapters import build_adapter
        self.adapter = build_adapter("smolvlm", meta={"model_name": "SmolVLM-500M-Instruct", "max_new_tokens": 64})
        if not self.adapter.available():
            self.load_error = str(getattr(self.adapter, "_load_error", "smolvlm adapter unavailable"))


def extract(image_path, task, mock_va=None):
    """returns {va_dict, parse_status(clean|failed), engine_error, raw_text}. VisionAnalysis 호환 dict."""
    if mock_va is not None:
        va = dict(mock_va)
        return {"va_dict": va, "parse_status": "clean", "engine_error": "",
                "raw_text": va.get("_raw_text", "")}
    try:
        rt = _SmolRuntime.get()
        rt.load()
        if rt.adapter is None or not rt.adapter.available():
            return {"va_dict": None, "parse_status": "failed",
                    "engine_error": rt.load_error or "smolvlm unavailable", "raw_text": ""}
        va = rt.adapter.analyze(Path(image_path), task, {"verification_type": task})
        return {"va_dict": va, "parse_status": "clean", "engine_error": "",
                "raw_text": va.get("_raw_text", "")}
    except Exception as exc:  # noqa: BLE001
        return {"va_dict": None, "parse_status": "failed",
                "engine_error": f"{type(exc).__name__}: {str(exc)[:300]}", "raw_text": ""}
