"""MagicVL-2B adapter — 스캐폴드 (모델 id/API 검증 필요).

주의(정직성):
에이전트 지식 기준으로 'MagicVL-2B' 의 정확한 공식 HF model id / 라이선스 / 추론 API 를 확신할 수 없다.
따라서 이 어댑터는 **검증 전 스캐폴드**이며, 아래를 확인한 뒤 사용해야 한다(런북 참고):
  1) HF 에 실제 존재하는 정확한 model id (예: 조직/MagicVL-2B)
  2) 추론 API 형태(MiniCPM 류 model.chat / Qwen 류 processor+generate / 기타 custom)
  3) 라이선스, 양자화 checkpoint 유무

구현 가정(검증되면 조정):
- trust_remote_code 로 AutoModel + AutoTokenizer 로딩
- MiniCPM 계열과 유사한 `model.chat(image=None, msgs=[...], tokenizer=...)` API 를 우선 시도하고,
  없으면 명확한 오류로 안내(자동 추측 남발 금지).
프롬프트/파서/판정은 SmolVLM 과 동일 재사용. 최종 PASS/FAIL 은 Rule Engine.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter
from .smolvlm_adapter import build_prompt, to_vision_analysis

# TODO(검증): 실제 공식 model id 로 교체. 미검증 placeholder.
_LOCAL_MODEL_PATH = "/data/models/MagicVL-2B"
_HF_MODEL_ID = "MagicVL-2B"  # UNVERIFIED — 런북의 존재확인 명령으로 정확한 id 확정 후 교체


class MagicVLAdapter(VLMAdapter):
    ADAPTER_KEY = "magicvl_2b"

    def __init__(self, meta: Optional[dict] = None):
        super().__init__(meta)
        model_path = self.meta.get("model_path") or _LOCAL_MODEL_PATH
        if Path(model_path).exists():
            self.model_id = model_path
        else:
            self.model_id = self.meta.get("model_id") or _HF_MODEL_ID
        self.max_new_tokens = int(self.meta.get("max_new_tokens", 128))
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._load_error: Optional[str] = None
        self.model_load_time_ms: float = 0.0
        self._try_load()

    def _try_load(self) -> None:
        t0 = time.perf_counter()
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            self._model = AutoModel.from_pretrained(
                self.model_id, trust_remote_code=True, torch_dtype=dtype
            )
            try:
                if torch.cuda.is_available():
                    self._model = self._model.to("cuda")
            except Exception:  # noqa: BLE001
                pass
            self._model = self._model.eval()
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._loaded = True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            self._loaded = False
        self.model_load_time_ms = round((time.perf_counter() - t0) * 1000, 3)

    def available(self) -> bool:
        return self._loaded

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        if not self._loaded:
            raise ModelNotAvailable(
                f"MagicVL-2B not loaded ({self._load_error or 'unknown'}). "
                "정확한 model id/추론 API 를 먼저 검증하세요(QWEN2VL_2B_RUNBOOK 형식의 MAGICVL 런북 참고)."
            )
        raw_text = self._infer(image_path, verification_type)
        normalized = to_vision_analysis(raw_text, verification_type, context)
        normalized["_raw_text"] = raw_text
        return normalized

    def _infer(self, image_path: Path, verification_type: str) -> str:
        import torch
        from PIL import Image

        prompt = build_prompt(verification_type)
        image = Image.open(str(image_path)).convert("RGB")
        chat = getattr(self._model, "chat", None)
        if not callable(chat):
            raise ModelNotAvailable(
                "MagicVL 모델에 .chat() API 가 없습니다. 실제 추론 인터페이스를 확인해 _infer 를 조정하세요."
            )
        msgs = [{"role": "user", "content": [image, prompt]}]
        with torch.inference_mode():
            out = chat(image=None, msgs=msgs, tokenizer=self._tokenizer,
                       sampling=False, max_new_tokens=self.max_new_tokens)
        if isinstance(out, (list, tuple)):
            out = out[0]
        return str(out).strip()
