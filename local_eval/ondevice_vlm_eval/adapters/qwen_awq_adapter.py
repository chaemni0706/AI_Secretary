"""Qwen2.5-VL-3B-AWQ adapter — 실제 추론 연결 (AWQ 4bit).

- 모델 클래스는 비양자화와 동일한 Qwen2_5_VLForConditionalGeneration 이며, AWQ 가중치는
  config 로 자동 감지된다(autoawq 필요). 추론 흐름은 기존 qwen batch runner
  (local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py)의 generate 부분을 미러링한다.
- 프롬프트/파서/판정은 SmolVLM 과 동일(build_prompt + to_vision_analysis + Rule Engine)
  → 다른 온디바이스 후보와 공정 비교(차이는 모델에서만 발생). analyze() 는 raw text 를 뽑아
  _raw_text 로 저장하고, evidence 만 정규화한다. 최종 PASS/FAIL 은 Rule Engine 이 결정한다.

의존성(torch/transformers/qwen_vl_utils)은 lazy 로드하며, 없으면 available()=False → 러너 SKIPPED.
가중치는 __init__ 에서 1회 로드하고, 실패해도 예외를 던지지 않고 available()=False 로만 신호한다.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter
from .smolvlm_adapter import build_prompt, to_vision_analysis  # 동일 프로토콜 재사용

_LOCAL_MODEL_PATH = "/data/models/Qwen2.5-VL-3B-Instruct-AWQ"
_HF_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"


class QwenAWQAdapter(VLMAdapter):
    ADAPTER_KEY = "qwen_awq"
    # 서브클래스가 override 하는 기본값(로딩 경로/모델 클래스/표시명). 3B 기본값은 유지.
    LOCAL_MODEL_PATH = _LOCAL_MODEL_PATH
    HF_MODEL_ID = _HF_MODEL_ID
    DISPLAY_NAME = "Qwen2.5-VL-3B-AWQ"

    def _model_class(self):
        """추론에 쓸 transformers 모델 클래스. Qwen2.5-VL 계열 기본."""
        from transformers import Qwen2_5_VLForConditionalGeneration
        return Qwen2_5_VLForConditionalGeneration

    def __init__(self, meta: Optional[dict] = None):
        super().__init__(meta)
        # 로컬 model_path 있으면 우선, 없으면 yaml model_id, 그것도 없으면 HF AWQ id.
        model_path = self.meta.get("model_path") or self.LOCAL_MODEL_PATH
        if Path(model_path).exists():
            self.model_id = model_path
        else:
            self.model_id = self.meta.get("model_id") or self.HF_MODEL_ID
        self.max_new_tokens = int(self.meta.get("max_new_tokens", 128))
        # AWQ Triton awq_gemm_kernel 은 fp16/bf16 혼합을 허용하지 않는다.
        # torch_dtype="auto" 는 일부 텐서를 bf16 으로 잡아 tl.dot 에서 dtype 충돌을 일으키므로
        # 반드시 float16 으로 고정한다(HF 권고: "set torch_dtype=torch.float16 ... with AWQ").
        self._model = None
        self._processor = None
        self._dtype = None
        self._loaded = False
        self._load_error: Optional[str] = None
        self.model_load_time_ms: float = 0.0
        self._try_load()

    # ------------------------------------------------------------------ #
    def _try_load(self) -> None:
        t0 = time.perf_counter()
        try:
            import torch
            from transformers import AutoProcessor

            model_cls = self._model_class()
            self._dtype = torch.float16  # AWQ 는 fp16 고정 (bf16/auto 금지)
            self._processor = AutoProcessor.from_pretrained(self.model_id)
            try:
                # 1차: device_map="auto" 로 로딩 (권장 경로)
                self._model = model_cls.from_pretrained(
                    self.model_id, torch_dtype=torch.float16, device_map="auto"
                )
            except Exception as exc_auto:  # noqa: BLE001
                # fallback: 단일 cuda 로딩 (device_map 관련 dtype/배치 문제 회피)
                self._load_error = f"device_map=auto 실패, 단일 cuda fallback 시도: {exc_auto}"
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self._model = model_cls.from_pretrained(
                    self.model_id, torch_dtype=torch.float16
                ).to(device)
            self._model.eval()
            self._loaded = True
            self._load_error = None
        except Exception as exc:  # noqa: BLE001 - 로드 실패는 available()=False 로만 신호
            self._load_error = str(exc)
            self._loaded = False
        self.model_load_time_ms = round((time.perf_counter() - t0) * 1000, 3)

    def available(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------ #
    def analyze(self, image_path: Path, verification_type: str, context: Optional[dict] = None) -> dict:
        if not self._loaded:
            raise ModelNotAvailable(
                f"{self.DISPLAY_NAME} not loaded ({self._load_error or 'unknown'}). "
                "torch/transformers/qwen_vl_utils/autoawq 가 설치된 env(예: conda qwen-vlm)에서 "
                f"실행하고, AWQ 가중치(로컬 또는 HF {self.HF_MODEL_ID})를 준비하세요."
            )
        raw_text = self._infer(image_path, verification_type)
        normalized = to_vision_analysis(raw_text, verification_type, context)  # SmolVLM 과 동일 파서
        normalized["_raw_text"] = raw_text
        return normalized

    def _infer(self, image_path: Path, verification_type: str) -> str:
        import torch
        from qwen_vl_utils import process_vision_info

        prompt = build_prompt(verification_type)  # SmolVLM 과 동일한 서술형 프롬프트
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": str(Path(image_path).resolve())},
                {"type": "text", "text": prompt},
            ],
        }]
        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self._processor(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        )
        # 텐서를 모델 device 로 이동. float 텐서(pixel_values 등)만 fp16 으로 캐스팅하고,
        # 정수 텐서(input_ids/attention_mask/image_grid_thw)는 dtype 을 바꾸지 않는다
        # (AWQ Triton kernel fp16/bf16 혼합 금지 → 입력도 fp16 통일).
        device = self._model.device
        for key, val in list(inputs.items()):
            if not hasattr(val, "to"):
                continue
            if torch.is_floating_point(val):
                inputs[key] = val.to(device=device, dtype=torch.float16)
            else:
                inputs[key] = val.to(device=device)
        with torch.inference_mode():
            generated_ids = self._model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False
            )
        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        return self._processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()


# ---------------------------------------------------------------------------
# Qwen2-VL-2B-Instruct(-AWQ) — 2B 경량 후보. 로딩 경로/모델 클래스만 다르고 나머지는 동일 재사용.
# ---------------------------------------------------------------------------

_QWEN2VL_2B_LOCAL_PATH = "/data/models/Qwen2-VL-2B-Instruct-AWQ"
_QWEN2VL_2B_HF_ID = "Qwen/Qwen2-VL-2B-Instruct-AWQ"


class Qwen2VL2BAdapter(QwenAWQAdapter):
    """Qwen2-VL-2B-Instruct-AWQ 어댑터.

    QwenAWQAdapter(3B) 의 로딩/추론/프롬프트/파서를 그대로 상속하고 아래만 다르다.
    - 모델 클래스: Qwen2VLForConditionalGeneration (Qwen2-VL 계열; 2.5 아님)
    - 기본 경로/ID: Qwen2-VL-2B-Instruct-AWQ (로컬 /data/models 우선, 없으면 HF id)
    AWQ fp16 고정/입력 캐스팅/negative-first 는 상속. 최종 판정은 Rule Engine.
    """

    ADAPTER_KEY = "qwen2vl_2b"
    LOCAL_MODEL_PATH = _QWEN2VL_2B_LOCAL_PATH
    HF_MODEL_ID = _QWEN2VL_2B_HF_ID
    DISPLAY_NAME = "Qwen2-VL-2B-AWQ"

    def _model_class(self):
        from transformers import Qwen2VLForConditionalGeneration
        return Qwen2VLForConditionalGeneration
