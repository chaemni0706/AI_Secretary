"""MiniCPM-V 2.6 adapter — 실제 추론 연결.

MiniCPM-V 계열은 표준 generate 가 아니라 custom `model.chat(image, msgs, tokenizer)` API 를 쓴다
(trust_remote_code 필요). 프롬프트/파서/판정은 SmolVLM 과 동일 재사용(build_prompt + to_vision_analysis
+ Rule Engine) → 다른 온디바이스 후보와 공정 비교. 최종 PASS/FAIL 은 Rule Engine 이 결정한다.

- 기본 모델: openbmb/MiniCPM-V-2_6 (bf16). int4 체크포인트(openbmb/MiniCPM-V-2_6-int4)나 로컬 경로도
  meta.model_id/model_path 로 지정 가능(로컬 우선).
- 의존성(torch/transformers/PIL)은 lazy 로드, 없으면 available()=False → 러너 SKIPPED.
- 가중치는 __init__ 에서 1회 로드하고, 실패해도 예외 없이 available()=False 로만 신호한다.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter
from .smolvlm_adapter import build_prompt, to_vision_analysis  # 동일 프로토콜 재사용

_LOCAL_MODEL_PATH = "/data/models/MiniCPM-V-2_6"
_HF_MODEL_ID = "openbmb/MiniCPM-V-2_6"


class MiniCPMVAdapter(VLMAdapter):
    ADAPTER_KEY = "minicpm_v"

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
            # int4 체크포인트는 이미 양자화되어 device_map 자동. bf16 은 로드 후 cuda 이동.
            self._model = AutoModel.from_pretrained(
                self.model_id, trust_remote_code=True, torch_dtype=dtype
            )
            try:
                if torch.cuda.is_available():
                    self._model = self._model.to("cuda")
            except Exception:  # noqa: BLE001 - int4 등 이미 배치된 경우 무시
                pass
            self._model = self._model.eval()
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=True
            )
            self._loaded = True
        except Exception as exc:  # noqa: BLE001 - 로드 실패는 available()=False 로만 신호
            self._load_error = str(exc)
            self._loaded = False
        self.model_load_time_ms = round((time.perf_counter() - t0) * 1000, 3)

    def available(self) -> bool:
        return self._loaded

    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        if not self._loaded:
            raise ModelNotAvailable(
                f"MiniCPM-V not loaded ({self._load_error or 'unknown'}). "
                "torch/transformers(trust_remote_code) 가 설치된 env(예: conda qwen-vlm)에서 실행하고, "
                f"가중치(로컬 또는 HF {_HF_MODEL_ID})를 준비하세요."
            )
        raw_text = self._infer(image_path, verification_type)
        normalized = to_vision_analysis(raw_text, verification_type, context)  # SmolVLM 과 동일 파서
        normalized["_raw_text"] = raw_text
        return normalized

    def _infer(self, image_path: Path, verification_type: str) -> str:
        import torch
        from PIL import Image

        prompt = build_prompt(verification_type)  # SmolVLM 과 동일한 서술형 프롬프트
        image = Image.open(str(image_path)).convert("RGB")
        msgs = [{"role": "user", "content": [image, prompt]}]
        with torch.inference_mode():
            out = self._model.chat(
                image=None, msgs=msgs, tokenizer=self._tokenizer,
                sampling=False, max_new_tokens=self.max_new_tokens,
            )
        # chat() 은 문자열을 반환(일부 버전은 (text, ...) 튜플) → 문자열만 취한다.
        if isinstance(out, (list, tuple)):
            out = out[0]
        return str(out).strip()


# ---------------------------------------------------------------------------
# MiniCPM-V 2.0 (2.8B) — 2.6(8B)보다 작은 variant. 로딩은 동일(AutoModel+tokenizer),
# chat() API 시그니처만 2.0 형식으로 override.
# ---------------------------------------------------------------------------

_V2_LOCAL_MODEL_PATH = "/data/models/MiniCPM-V-2"
_V2_HF_MODEL_ID = "openbmb/MiniCPM-V-2"


class MiniCPMV2Adapter(MiniCPMVAdapter):
    """MiniCPM-V 2.0 (openbmb/MiniCPM-V-2, ~2.8B) 어댑터.

    MiniCPMVAdapter(2.6)의 로딩/프롬프트/파서를 상속하고 아래만 다르다.
    - 기본 경로/ID: openbmb/MiniCPM-V-2 (로컬 /data/models/MiniCPM-V-2 우선)
    - chat() 시그니처: 2.0 은 image 를 인자로 받고 content 는 문자열, (res, context, _) 튜플 반환.
      (2.6 은 image=None + content=[image, text], 문자열 반환)
    실제 API 는 모델 카드 기준이며, smoke test 로 검증 후 필요 시 조정한다.
    최종 판정은 Rule Engine.
    """

    ADAPTER_KEY = "minicpm_v2"

    def __init__(self, meta: Optional[dict] = None):
        meta = dict(meta or {})
        model_path = meta.get("model_path") or _V2_LOCAL_MODEL_PATH
        if Path(model_path).exists():
            meta["model_id"] = model_path
        elif not meta.get("model_id"):
            meta["model_id"] = _V2_HF_MODEL_ID
        super().__init__(meta)

    def _infer(self, image_path: Path, verification_type: str) -> str:
        import torch
        from PIL import Image

        prompt = build_prompt(verification_type)
        image = Image.open(str(image_path)).convert("RGB")
        msgs = [{"role": "user", "content": prompt}]  # 2.0: content 는 문자열
        with torch.inference_mode():
            out = self._model.chat(
                image=image, msgs=msgs, context=None,
                tokenizer=self._tokenizer, sampling=False,
            )
        # 2.0 chat 은 (res, context, _) 튜플 반환 → 첫 요소(res) 사용.
        if isinstance(out, (list, tuple)):
            out = out[0]
        return str(out).strip()
