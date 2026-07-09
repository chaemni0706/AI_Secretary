"""SmolVLM adapter — 실제 추론 연결 (SmolVLM-500M-Instruct).

흐름:
    image → SmolVLM 추론(raw_text, 단답 label) → Python parser로 label 정규화
          → VisionAnalysis 호환 dict(water_visual_evidence=[label]) (+ _raw_text)

SmolVLM-500M은 JSON을 안정적으로 만들지 못하고 단답 label을 낸다. 따라서 water 인증은
"허용 label 중 하나"를 출력하게 하고, Python 후처리로 VisionAnalysis-compatible dict를 만든다.
최종 PASS/FAIL은 이 어댑터가 아니라 러너가 호출하는 Rule Engine이 결정한다.

의존성(torch/transformers/PIL)은 lazy 로드하며, 없으면 available()=False → 러너가 SKIPPED 처리.
가중치는 __init__ 에서 1회 로드하고, 실패해도 예외를 던지지 않고 available()=False 로만 신호한다
(torch 없는 base 환경/기존 테스트 호환).
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Optional

from .base import ModelNotAvailable, VLMAdapter

# 기존 normalizer(exercise/study) 재사용을 위해 qwen_vlm_eval/scripts 를 import 경로에 추가.
_QWEN_SCRIPTS = Path(__file__).resolve().parents[2] / "qwen_vlm_eval" / "scripts"
if str(_QWEN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_QWEN_SCRIPTS))

# SmolVLM water 단답 허용 label. insufficient_evidence 는 스키마 enum 이 아니라 fallback 표식.
WATER_ALLOWED_LABELS = (
    "visible_water",
    "visible_clear_liquid",
    "filled_container",
    "empty_container",
    "non_water_beverage",
    "insufficient_evidence",
)
# 실제 WaterVisualEvidence enum 에 존재하는 값 (VisionAnalysis 검증 통과용)
_WATER_SCHEMA_LABELS = {
    "visible_water", "visible_clear_liquid", "filled_container",
    "empty_container", "non_water_beverage",
}
# label 추출 우선순위 (구체/부정 우선; 부분 문자열 충돌 방지)
_WATER_LABEL_PRIORITY = (
    "non_water_beverage",
    "empty_container",
    "filled_container",
    "visible_clear_liquid",
    "visible_water",
    "insufficient_evidence",
)

_LOCAL_MODEL_PATH = "/data/models/SmolVLM-500M-Instruct"
_HF_MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"


class SmolVLMAdapter(VLMAdapter):
    ADAPTER_KEY = "smolvlm"

    def __init__(self, meta: Optional[dict] = None):
        super().__init__(meta)
        # 로컬 가중치 경로가 있으면 우선 사용, 없으면 HF id.
        self.model_id = self.meta.get("model_id") or (
            _LOCAL_MODEL_PATH if Path(_LOCAL_MODEL_PATH).exists() else _HF_MODEL_ID
        )
        self.max_new_tokens = int(self.meta.get("max_new_tokens", 32))
        self._model = None
        self._processor = None
        self._device = "cpu"
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
            from transformers import AutoModelForImageTextToText, AutoProcessor

            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if self._device == "cuda" else torch.float32
            self._dtype = dtype
            self._model = AutoModelForImageTextToText.from_pretrained(
                self.model_id, torch_dtype=dtype
            ).to(self._device)
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
                f"SmolVLM not loaded ({self._load_error or 'unknown'}). "
                "torch/transformers 가 설치된 환경(예: conda qwen-vlm)에서 실행하세요."
            )
        raw_text = self._infer(image_path, verification_type)
        normalized = to_vision_analysis(raw_text, verification_type, context)
        normalized["_raw_text"] = raw_text  # 러너가 raw_outputs/ 에 저장
        return normalized

    def _infer(self, image_path: Path, verification_type: str) -> str:
        import torch
        from PIL import Image

        prompt = _build_prompt(verification_type)
        image = Image.open(str(image_path)).convert("RGB")
        messages = [{
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": prompt}],
        }]
        chat_text = self._processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self._processor(text=chat_text, images=[image], return_tensors="pt")
        inputs = self._move_inputs(inputs)
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, do_sample=False
            )
        trimmed = generated[:, inputs["input_ids"].shape[1]:]
        return self._processor.batch_decode(trimmed, skip_special_tokens=True)[0].strip()

    def _move_inputs(self, inputs):
        """processor 출력 텐서를 실행 device 로 이동.

        SmolVLM-500M 은 (기존 동작 그대로) device 이동만 한다.
        dtype 캐스팅은 SmolVLM2Adapter 에서 override 한다(2.2B 는 pixel_values dtype 불일치 발생).
        """
        return inputs.to(self._device)


# ---------------------------------------------------------------------------
# SmolVLM2-2.2B-Instruct — 동일 프롬프트/파서 재사용, 로딩 경로/dtype 만 분리
# ---------------------------------------------------------------------------

_SMOLVLM2_LOCAL_PATH = "/data/models/SmolVLM2-2.2B-Instruct"
_SMOLVLM2_HF_ID = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"


class SmolVLM2Adapter(SmolVLMAdapter):
    """SmolVLM2-2.2B-Instruct 어댑터.

    SmolVLMAdapter 의 프롬프트/파서/추론 흐름을 그대로 상속하고, 아래만 다르다.
    - 기본 모델 경로/ID 를 2.2B 로 해석(로컬 /data/models 우선, 없으면 HF id).
    - 기본 max_new_tokens 를 128 로(2.2B 서술 출력이 더 길다).
    - processor 출력 float 텐서(pixel_values)를 모델 dtype(bfloat16)으로 캐스팅
      (2.2B 는 캐스팅 없으면 'Input FloatTensor vs weight BFloat16Type' 오류).
    최종 PASS/FAIL 은 이 어댑터가 아니라 Rule Engine 이 결정한다.
    """

    ADAPTER_KEY = "smolvlm2_2b"

    def __init__(self, meta: Optional[dict] = None):
        meta = dict(meta or {})
        # 로컬 다운로드(/data/models/...) 가 있으면 우선, 없으면 yaml model_id, 그것도 없으면 HF id.
        model_path = meta.get("model_path") or _SMOLVLM2_LOCAL_PATH
        if Path(model_path).exists():
            meta["model_id"] = model_path
        elif not meta.get("model_id"):
            meta["model_id"] = _SMOLVLM2_HF_ID
        meta.setdefault("max_new_tokens", 128)
        super().__init__(meta)

    def _move_inputs(self, inputs):
        # float 텐서만 모델 dtype 으로 캐스팅됨(정수 input_ids 는 BatchFeature.to 가 유지).
        return inputs.to(self._device, dtype=self._dtype)


# ---------------------------------------------------------------------------
# 프롬프트 (소형 모델 → 단답 label 유도)
# ---------------------------------------------------------------------------

def _build_prompt(verification_type: str) -> str:
    if verification_type == "water":
        # 소형 모델이 label 리스트를 그대로 따라 읽는(parroting) 문제를 피하려고,
        # label 나열 대신 '짧은 서술'을 요청한다. 서술 문구는 파서가 복합 evidence로 매핑한다.
        return (
            "Look only at what is visible in this photo. Ignore any numbers or brand text. "
            "Describe the drink container and what is inside it. "
            "Only say 'water' if you can clearly see water or clear liquid inside the container. "
            "If there is a drink, say what it is; if the container has nothing in it, say so. "
            "Name the container (glass, cup, bottle, tumbler). "
            "In a few words (examples: 'a glass of water', 'a glass with water inside', "
            "'a bottle of water', 'a cup of coffee', 'a mug of tea')."
        )
    if verification_type == "exercise":
        # water 와 동일하게 label 나열 대신 '짧은 서술' 요청(parroting 회피).
        # 서술 문구는 normalize_exercise_output 이 gym/home 별 evidence 로 매핑한다.
        return (
            "Look only at what is visible in this photo. Ignore any text or numbers. "
            "Name the specific exercise equipment if present (dumbbell, barbell, treadmill, "
            "weight machine, kettlebell, resistance band, exercise mat), and say whether a person "
            "is doing a workout pose (squat, push-up, plank, lunge, stretching). "
            "Also say if it looks like a gym or a home workout space. "
            "In a few words (examples: 'dumbbells in a gym', 'a treadmill', 'a barbell on a rack', "
            "'a weight machine', 'a person doing a squat on an exercise mat at home', "
            "'an office desk', 'a bedroom', 'a plate of food', 'an empty room', "
            "'running shoes only', 'a water bottle only')."
        )
    if verification_type == "study":
        # 서술형+예시 (label 나열 회피). 문구는 파서가 study evidence 로 매핑한다.
        return (
            "Look only at what is visible in this photo. Ignore brand text. "
            "In a few words, describe the study materials or the screen content. "
            "If it is a single sheet or page, say what it is (a textbook page, a printed worksheet, "
            "a page of practice problems, handwritten notes). "
            "(examples: 'an open textbook with handwritten notes', 'a workbook with math problems', "
            "'a printed worksheet with problems', 'a textbook page with highlighted text', "
            "'a highlighted textbook', 'a coding screen', 'a lecture video on a laptop', "
            "'a PDF document on screen', 'a study timer', 'playing a video game', "
            "'watching YouTube', 'Instagram social media', 'online shopping', "
            "'just a closed laptop', 'a blank monitor')."
        )
    return "Describe what is visible in this image in one short sentence."


# ---------------------------------------------------------------------------
# 단답 label 정규화 (water)
# ---------------------------------------------------------------------------

def normalize_water_label(raw_text: str) -> str:
    """SmolVLM raw 출력 → 허용 label 하나. 없으면 insufficient_evidence.

    - 소문자화, 앞뒤 공백 제거, 마침표/쉼표 제거, 'Assistant:' 류 prefix 제거
    - 하이픈/공백을 언더스코어로 통일 후 허용 label 부분 문자열 매칭
    """
    low = str(raw_text).lower().strip()
    # 'assistant:' 등 role prefix 제거 (마지막 발화만)
    for sep in ("assistant:", "answer:", "label:"):
        if sep in low:
            low = low.split(sep)[-1]
    low = low.replace(".", " ").replace(",", " ").replace("-", "_")
    low = " ".join(low.split())            # 공백 정리
    underscored = low.replace(" ", "_")
    for label in _WATER_LABEL_PRIORITY:
        if label in underscored:
            return label
    return "insufficient_evidence"


# --- 2차: 복수 evidence 추출 (단답/comma-separated/문구 모두 지원) ---

# 문구 → 복합 evidence label 매핑 (PASS 근거는 컨테이너+물+채움을 함께 부여)
_WATER_PHRASE_LABELS: tuple[tuple[str, frozenset], ...] = (
    ("full glass of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("half glass of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("glass of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("cup of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("glass of clear water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water in the glass", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water in a glass", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water in glass", frozenset({"container_present", "visible_water", "filled_container"})),
    ("filled cup", frozenset({"container_present", "filled_container", "visible_water"})),
    ("filled glass", frozenset({"container_present", "filled_container", "visible_water"})),
    ("filled with water", frozenset({"container_present", "filled_container", "visible_water"})),
    # 투명 용기 내부 물(약하게 보여도) — 반드시 'water/clear liquid' 단어가 있을 때만 매핑(FP 안전)
    ("glass filled with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("transparent glass with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("clear glass with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("clear glass of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water inside", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water in it", frozenset({"container_present", "visible_water", "filled_container"})),
    ("containing water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water fills", frozenset({"container_present", "visible_water", "filled_container"})),
    ("partly full of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("bottle with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("clear liquid in glass", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    ("clear liquid in a glass", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    ("clear liquid in the glass", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    ("clear liquid in cup", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    # 용기 '이름'만으로는 물 존재를 단정하지 않는다(빈 water bottle 도 'water bottle' 로 불림 → FP).
    # container_present 만 부여하고, 실제 물/액체 존재 문구(아래)가 있을 때만 visible_water/filled 를 준다.
    ("water bottle with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("water bottle", frozenset({"container_present"})),
    ("bottle of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("bottle with water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("holding water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("holding a glass of water", frozenset({"container_present", "visible_water", "filled_container"})),
    ("clear liquid in container", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    ("clear liquid in a container", frozenset({"container_present", "visible_clear_liquid", "filled_container"})),
    ("filling a cup", frozenset({"container_present", "visible_water", "filled_container"})),
    ("filling the cup", frozenset({"container_present", "visible_water", "filled_container"})),
    ("filling a glass", frozenset({"container_present", "visible_water", "filled_container"})),
    ("dispenser filling", frozenset({"container_present", "visible_water", "filled_container"})),
    ("clear liquid", frozenset({"visible_clear_liquid"})),
    ("visible water", frozenset({"visible_water"})),
    ("water is visible", frozenset({"visible_water"})),
    ("clear water", frozenset({"visible_water"})),
    # 단독 'water' 는 매핑하지 않는다: 'water bottle'/'water glass'/'a glass for water' 처럼
    # 빈 용기의 '이름'에도 water 가 들어가 FP 를 유발하기 때문. 실제 물 존재는 위의 명시 문구로만 인정.
    # 부정(= PASS 근거 아님): 아래는 절대 positive 로 올리지 않는다
    # 빈 상태는 '명확한 빈 상태 표현'에서만 매핑한다. 단독 "empty" 는 매핑하지 않는다
    # (소형 모델이 프롬프트/설명에서 'empty' 를 흘리면 모든 물을 empty 로 오판하기 때문).
    ("empty glass", frozenset({"empty_container"})),
    ("empty cup", frozenset({"empty_container"})),
    ("empty bottle", frozenset({"empty_container"})),
    ("empty container", frozenset({"empty_container"})),
    ("empty tumbler", frozenset({"empty_container"})),
    ("empty mug", frozenset({"empty_container"})),
    ("nearly empty", frozenset({"empty_container"})),
    ("no water", frozenset({"empty_container"})),
    ("no liquid", frozenset({"empty_container"})),
    ("without water", frozenset({"empty_container"})),
    ("coffee", frozenset({"non_water_beverage"})),
    ("tea", frozenset({"non_water_beverage"})),
    ("juice", frozenset({"non_water_beverage"})),
    ("soda", frozenset({"non_water_beverage"})),
    ("colored beverage", frozenset({"non_water_beverage"})),
    ("colored liquid", frozenset({"non_water_beverage"})),
    ("closed bottle", frozenset()),  # 근거 부족 → insufficient (positive 없음)
)
_WATER_MULTI_LABELS = (
    "container_present", "visible_water", "visible_clear_liquid",
    "filled_container", "empty_container", "non_water_beverage",
)


def extract_water_labels(raw_text: str) -> tuple[set, str]:
    """raw_text → 허용 water evidence label 집합 (explicit label + 문구 매핑)."""
    low = str(raw_text).lower().replace("-", "_")
    low = " ".join(low.replace(".", " ").replace(",", " ").split())
    underscored = low.replace(" ", "_")
    labels: set = set()
    for lab in _WATER_MULTI_LABELS:
        if lab in underscored:
            labels.add(lab)
    for phrase, labs in _WATER_PHRASE_LABELS:
        if phrase in low:
            labels |= set(labs)
    return labels, low


def _apply_water_implications(labels: set) -> set:
    """MVP 규칙: 컨테이너+물이면 PASS 근거를 완성. 단, 부정(empty/non_water)이 있으면 완성하지 않는다."""
    negative = labels & {"empty_container", "non_water_beverage"}
    if negative:
        return labels  # 빈 컵/색 음료 등은 PASS 근거로 올리지 않음
    liquid = labels & {"visible_water", "visible_clear_liquid"}
    if "filled_container" in labels:
        labels.add("container_present")
        if not liquid:
            labels.add("visible_water")
            liquid = {"visible_water"}
    if liquid:
        labels.add("container_present")  # 물이 보이면 담는 용기가 있다고 본다
    if "container_present" in labels and liquid:
        labels.add("filled_container")
    return labels


def _container_label_from_text(low: str) -> str:
    if "glass" in low:
        return "glass"
    if "bottle" in low:
        return "water_bottle"
    if "tumbler" in low:
        return "tumbler"
    return "cup"  # container_present 인데 구체 언급 없으면 일반 cup


def _water_vision_analysis(raw_text: str) -> dict:
    """SmolVLM raw_text → 복수 water evidence VisionAnalysis 호환 dict."""
    labels, low = extract_water_labels(raw_text)
    labels = _apply_water_implications(labels)

    objects = []
    if "container_present" in labels:
        objects = [{"label": _container_label_from_text(low), "confidence": 0.6, "evidence": None}]

    water_ev = [t for t in ("visible_water", "visible_clear_liquid", "filled_container",
                            "empty_container", "non_water_beverage") if t in labels]
    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None,
        "objects": objects,
        "visible_text": [],
        "visual_evidence": [],
        "water_visual_evidence": water_ev,
        "study_visual_evidence": [],
        "exercise_visual_evidence": [],
    }


# ---------------------------------------------------------------------------
# study evidence 추출 (문구 → study enum 토큰 복수; 모델은 판정하지 않음)
# ---------------------------------------------------------------------------

_STUDY_PHRASE_LABELS: tuple[tuple[str, frozenset], ...] = (
    # 긍정 (종이 학습)
    ("open textbook", frozenset({"open_textbook"})),
    ("textbook", frozenset({"open_textbook"})),
    ("study book", frozenset({"open_textbook"})),
    ("open book", frozenset({"open_textbook"})),
    ("reading a book", frozenset({"open_textbook"})),
    ("a book", frozenset({"open_textbook"})),  # 'a book'는 'notebook'/'textbook' 부분문자열과 충돌하지 않음
    ("workbook", frozenset({"open_workbook"})),
    ("exercise book", frozenset({"open_workbook"})),
    ("problem book", frozenset({"open_workbook"})),
    # 종이 한 장 형태의 학습 자료(문제지/프린트/교재 페이지) → 기존 study enum 으로 매핑(FP 안전:
    # 게임/SNS/엔터테인먼트 문구와 겹치지 않음). 새 토큰은 스키마에 없으므로 만들지 않는다.
    ("textbook page", frozenset({"open_textbook"})),
    ("page of a textbook", frozenset({"open_textbook"})),
    ("study page", frozenset({"open_textbook"})),
    ("study sheet", frozenset({"problem_solving_material"})),
    ("study material", frozenset({"open_textbook"})),
    ("learning material", frozenset({"open_textbook"})),
    ("printed learning material", frozenset({"open_textbook"})),
    ("printed material", frozenset({"open_textbook"})),
    ("printed notes", frozenset({"handwritten_notes"})),
    ("practice sheet", frozenset({"problem_solving_material"})),
    ("problem sheet", frozenset({"problem_solving_material"})),
    ("page of problems", frozenset({"problem_solving_material"})),
    ("printed problems", frozenset({"problem_solving_material"})),
    ("a4 sheet", frozenset({"problem_solving_material"})),
    ("answer sheet", frozenset({"problem_solving_material"})),
    ("handwritten", frozenset({"handwritten_notes"})),
    ("handwriting", frozenset({"handwritten_notes"})),
    ("taking notes", frozenset({"handwritten_notes"})),
    ("written notes", frozenset({"handwritten_notes"})),
    ("notebook", frozenset({"handwritten_notes"})),
    ("notes", frozenset({"handwritten_notes"})),
    ("highlighted", frozenset({"highlighted_text"})),
    ("highlighter", frozenset({"highlighted_text"})),
    ("highlight", frozenset({"highlighted_text"})),
    ("math problem", frozenset({"problem_solving_material"})),
    ("solving problem", frozenset({"problem_solving_material"})),
    ("practice problem", frozenset({"problem_solving_material"})),
    ("worksheet", frozenset({"problem_solving_material"})),
    ("problem set", frozenset({"problem_solving_material"})),
    # 긍정 (디지털 학습)
    ("lecture video", frozenset({"lecture_video"})),
    ("video lecture", frozenset({"lecture_video"})),
    ("online class", frozenset({"lecture_video"})),
    ("lecture", frozenset({"lecture_video"})),
    ("pdf", frozenset({"educational_document"})),
    ("document on screen", frozenset({"educational_document"})),
    ("educational document", frozenset({"educational_document"})),
    ("slides", frozenset({"educational_document"})),
    ("code editor", frozenset({"code_editor"})),
    ("coding", frozenset({"code_editor"})),
    ("source code", frozenset({"code_editor"})),
    ("programming", frozenset({"code_editor"})),
    ("code", frozenset({"code_editor"})),
    ("study screen", frozenset({"study_content_on_screen"})),
    ("study app", frozenset({"study_content_on_screen"})),
    ("learning app", frozenset({"study_content_on_screen"})),
    ("study content", frozenset({"study_content_on_screen"})),
    ("study timer", frozenset({"study_timer"})),
    ("pomodoro", frozenset({"study_timer"})),
    # 부정 (우선 거절)
    ("video game", frozenset({"gaming_content"})),
    ("gaming", frozenset({"gaming_content"})),
    ("playing a game", frozenset({"gaming_content"})),
    ("game", frozenset({"gaming_content"})),
    ("youtube", frozenset({"entertainment_video"})),
    ("netflix", frozenset({"entertainment_video"})),
    ("movie", frozenset({"entertainment_video"})),
    ("tv show", frozenset({"entertainment_video"})),
    ("streaming", frozenset({"entertainment_video"})),
    ("entertainment", frozenset({"entertainment_video"})),
    ("instagram", frozenset({"social_media"})),
    ("social media", frozenset({"social_media"})),
    ("facebook", frozenset({"social_media"})),
    ("twitter", frozenset({"social_media"})),
    ("messenger", frozenset({"social_media"})),
    ("online shopping", frozenset({"shopping_content"})),
    ("shopping", frozenset({"shopping_content"})),
    ("online store", frozenset({"shopping_content"})),
    ("product page", frozenset({"shopping_content"})),
    # 불확실 / 기기만 (retake 쪽)
    ("closed book", frozenset({"uncertain_screen_content"})),
    ("closed textbook", frozenset({"uncertain_screen_content"})),
    ("closed laptop", frozenset({"uncertain_screen_content"})),
    ("blank screen", frozenset({"uncertain_screen_content"})),
    ("blank monitor", frozenset({"uncertain_screen_content"})),
    ("empty desk", frozenset({"uncertain_screen_content"})),
    ("just a laptop", frozenset({"uncertain_screen_content"})),
    ("laptop only", frozenset({"uncertain_screen_content"})),
    ("monitor only", frozenset({"uncertain_screen_content"})),
    # 기기만 언급(내용 불명) → 불확실. 실제 학습 콘텐츠가 함께 있으면 Rule Engine이 uncertain 을 무시한다.
    ("laptop", frozenset({"uncertain_screen_content"})),
    ("monitor", frozenset({"uncertain_screen_content"})),
    ("tablet", frozenset({"uncertain_screen_content"})),
    ("computer", frozenset({"uncertain_screen_content"})),
    ("screen", frozenset({"uncertain_screen_content"})),
)
_STUDY_PAPER = {"open_textbook", "open_workbook", "handwritten_notes", "highlighted_text",
                "problem_solving_material", "educational_document"}
_STUDY_SCREEN = {"study_content_on_screen", "lecture_video", "code_editor"}


def extract_study_labels(raw_text: str) -> set:
    low = str(raw_text).lower().replace("-", "_")
    low = " ".join(low.replace(".", " ").replace(",", " ").split())
    from normalize_qwen_output import STUDY_EVIDENCE
    labels: set = set()
    underscored = low.replace(" ", "_")
    for tok in STUDY_EVIDENCE:               # explicit enum 토큰 직접 언급
        if tok in underscored:
            labels.add(tok)
    for phrase, labs in _STUDY_PHRASE_LABELS:
        if phrase in low:
            labels |= set(labs)
    return labels


def _study_vision_analysis(raw_text: str) -> dict:
    labels = extract_study_labels(raw_text)
    paper = labels & _STUDY_PAPER
    screen = labels & _STUDY_SCREEN
    # 학습 콘텐츠가 있으면 관련 사물을 보강(점수 캡 10 + highlighted_text 의 종이 근거 충족).
    objects = []
    if paper:
        objects += [{"label": "notebook", "confidence": 0.6, "evidence": None},
                    {"label": "pen", "confidence": 0.6, "evidence": None},
                    {"label": "desk", "confidence": 0.6, "evidence": None}]
    if screen:
        objects += [{"label": "laptop", "confidence": 0.6, "evidence": None},
                    {"label": "monitor", "confidence": 0.6, "evidence": None}]
    study_ev = sorted(labels)  # 모두 STUDY_EVIDENCE enum 값
    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None,
        "objects": objects,
        "visible_text": [],
        "visual_evidence": [],
        "water_visual_evidence": [],
        "study_visual_evidence": study_ev,
        "exercise_visual_evidence": [],
    }


def to_vision_analysis(raw_text: str, verification_type: str, context: Optional[dict] = None) -> dict:
    """raw_text → VisionAnalysis 호환 dict.

    water: 단답 label 프로토콜(허용 label → water_visual_evidence=[label]).
    exercise/study: 서술문을 기존 normalizer로 정규화(부가 지원; 이번 범위는 water 우선).
    """
    if verification_type == "water":
        return _water_vision_analysis(raw_text)

    if verification_type == "exercise":
        from normalize_exercise_output import normalize_exercise_evidence
        raw = {"objects": [], "visual_evidence": [{"description": raw_text}],
               "scenes": [{"description": raw_text}]}
        return normalize_exercise_evidence(raw, (context or {}).get("exercise_activity_type"))

    if verification_type == "study":
        return _study_vision_analysis(raw_text)

    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None, "objects": [], "visible_text": [], "visual_evidence": [],
        "water_visual_evidence": [], "study_visual_evidence": [], "exercise_visual_evidence": [],
    }


# 다른 온디바이스 어댑터(MobileVLM 등)가 동일 프로토콜(프롬프트+파서)을 재사용하도록 공개 별칭.
build_prompt = _build_prompt
