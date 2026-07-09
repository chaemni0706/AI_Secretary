"""MobileVLM V2 adapter — 실제 추론 연결 (MobileVLM_V2-1.7B, mtgv repo).

mtgv MobileVLM 은 HF 표준 auto-class 로 로드되지 않는다(MobileLlamaForCausalLM, model_type "mobilevlm").
공식 repo(github.com/Meituan-AutoML/MobileVLM, /data/repos/MobileVLM)의 API 를 사용한다:
  from mobilevlm.model.mobilevlm import load_pretrained_model
  from mobilevlm.conversation import conv_templates, SeparatorStyle
  from mobilevlm.utils import disable_torch_init, process_images, tokenizer_image_token, KeywordsStoppingCriteria
  from mobilevlm.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN

핵심:
- scripts/inference.py 의 `inference_once` 는 이미지마다 모델을 재로드하고 결과를 print 만 하므로 쓰지 않는다.
- 대신 __init__ 에서 load_pretrained_model 을 1회만 호출해 (tokenizer, model, image_processor) 를 보관하고,
  analyze() 에서는 generate 부분만 재사용해 raw text 를 return 한다(_raw_text 로 저장).
- 프롬프트/파서/판정은 SmolVLM 과 동일(build_prompt + to_vision_analysis + Rule Engine) → 공정 비교.

의존성/가중치가 없으면 available()=False → 러너 SKIPPED (환경 무손상).
권장 실행 환경: mtgv 전용 conda env (torch 2.0.x, transformers 4.33.x, PYTHONPATH=/data/repos/MobileVLM).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter
from .smolvlm_adapter import build_prompt, to_vision_analysis  # 동일 프로토콜 재사용

_LOCAL_MODEL_PATH = "/data/models/MobileVLM_V2-1.7B"
_HF_MODEL_ID = "mtgv/MobileVLM_V2-1.7B"


class MobileVLMAdapter(VLMAdapter):
    ADAPTER_KEY = "mobilevlm"

    def __init__(self, meta: Optional[dict] = None):
        super().__init__(meta)
        self.model_id = self.meta.get("model_id") or (
            _LOCAL_MODEL_PATH if Path(_LOCAL_MODEL_PATH).exists() else _HF_MODEL_ID
        )
        self.conv_mode = self.meta.get("conv_mode", "v1")
        self.max_new_tokens = int(self.meta.get("max_new_tokens", 48))
        self._tokenizer = None
        self._model = None
        self._image_processor = None
        self._loaded = False
        self._load_error: Optional[str] = None
        self.model_load_time_ms: float = 0.0
        self._try_load()

    # ------------------------------------------------------------------ #
    def _try_load(self) -> None:
        t0 = time.perf_counter()
        try:
            from mobilevlm.model.mobilevlm import load_pretrained_model
            from mobilevlm.utils import disable_torch_init

            disable_torch_init()
            # load_pretrained_model(model_path, load_8bit=False, load_4bit=False)
            #   -> (tokenizer, model, image_processor, context_len)
            self._tokenizer, self._model, self._image_processor, _ = load_pretrained_model(
                self.model_id, False, False
            )
            self._model.eval()
            self._loaded = True
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
                f"MobileVLM not loaded ({self._load_error or 'unknown'}). "
                "mtgv 'mobilevlm' repo + 가중치가 있는 환경에서 실행하세요 "
                "(PYTHONPATH=/data/repos/MobileVLM, torch 2.0.x / transformers 4.33.x)."
            )
        raw_text = self._infer(image_path, verification_type)
        normalized = to_vision_analysis(raw_text, verification_type, context)  # SmolVLM 과 동일 파서
        normalized["_raw_text"] = raw_text
        return normalized

    def _infer(self, image_path: Path, verification_type: str) -> str:
        """scripts/inference.py 의 generate 부분만 재사용 (모델은 이미 로드됨)."""
        import torch
        from PIL import Image

        from mobilevlm.constants import DEFAULT_IMAGE_TOKEN, IMAGE_TOKEN_INDEX
        from mobilevlm.conversation import SeparatorStyle, conv_templates
        from mobilevlm.utils import (
            KeywordsStoppingCriteria,
            process_images,
            tokenizer_image_token,
        )

        model = self._model
        tokenizer = self._tokenizer
        prompt = build_prompt(verification_type)  # SmolVLM 과 동일한 서술형 프롬프트

        images = [Image.open(str(image_path)).convert("RGB")]
        images_tensor = process_images(images, self._image_processor, model.config).to(
            model.device, dtype=torch.float16
        )

        conv = conv_templates[self.conv_mode].copy()
        conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + "\n" + prompt)
        conv.append_message(conv.roles[1], None)
        prompt_str = conv.get_prompt()
        stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2

        input_ids = (
            tokenizer_image_token(prompt_str, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt")
            .unsqueeze(0)
            .to(model.device)
        )
        stopping_criteria = KeywordsStoppingCriteria([stop_str], tokenizer, input_ids)
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_tensor,
                do_sample=False,
                temperature=0.0,
                num_beams=1,
                max_new_tokens=self.max_new_tokens,
                use_cache=True,
                stopping_criteria=[stopping_criteria],
            )
        input_token_len = input_ids.shape[1]
        outputs = tokenizer.batch_decode(
            output_ids[:, input_token_len:], skip_special_tokens=True
        )[0].strip()
        if stop_str and outputs.endswith(stop_str):
            outputs = outputs[: -len(stop_str)]
        return outputs.strip()
