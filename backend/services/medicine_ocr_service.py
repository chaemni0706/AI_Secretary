"""약봉투 이미지 OCR 분석 및 약 정보 파싱 서비스.

paddleocr 는 선택적(optional) 의존성이다. 모듈 최상단에서 import 하지 않고
실제 OCR 실행 시점에 lazy import 하므로, paddleocr 가 설치되어 있지 않아도
이 모듈(및 이 모듈을 import 하는 라우터)과 FastAPI 앱 전체는 정상 기동된다.
미설치 상태에서 OCR 을 호출하면 명확한 RuntimeError 를 던진다.
"""

import os

# PaddleOCR import 전에 반드시 설정해야 하는 환경변수 (import 시점에 맞춰 미리 설정)
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import re

_ocr_engine = None


def _get_ocr_engine():
    """PaddleOCR 엔진을 최초 호출 시 한 번만 로드한다.

    paddleocr 를 여기서 lazy import 한다. 미설치 시 RuntimeError 를 던져
    라우터가 500 대신 명확한 optional-dependency 오류를 반환할 수 있게 한다.
    """
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "paddleocr가 설치되어 있지 않습니다. Medicine OCR 기능을 사용하려면 "
                "paddleocr를 설치하세요 (pip install paddleocr)."
            ) from exc
        _ocr_engine = PaddleOCR(lang="korean")
    return _ocr_engine


def extract_ocr_lines(image_path: str):
    """이미지에서 (텍스트, 신뢰도) 튜플 리스트를 추출한다."""
    engine = _get_ocr_engine()
    results = engine.predict(image_path)
    if not results:
        return []

    result = results[0]
    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    return list(zip(texts, scores))


# OCR 오인식 보정 규칙 (복용 정보 줄에만 적용)
DOSE_TEXT_CORRECTIONS = {
    "m3": "ml",
    "m1": "ml",
    "mI": "ml",
    "최": "씩",
    "책": "씩",
    "씨": "씩",
    "식": "씩",
    "문": "분",
    "뿐": "분",
}

DOSE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(정|캡슐|포|병|환|알|mg|g|ml)\s*씩\s*(\d+)\s*회\s*(\d+)\s*일?\s*분?"
)

MEDICINE_NAME_KEYWORDS = ["정", "시럽", "과립", "현탁액", "캡슐", "액", "mg", "g"]

# 약 이름으로 오인식되면 안 되는 안내 문구
EXCLUDED_NAME_SUBSTRINGS = [
    "약정보",
    "약품사진",
    "약품명",
    "복약안내",
    "주의",
    "안내",
    "분류",
]


def _apply_dose_corrections(text: str) -> str:
    corrected = text
    for wrong, right in DOSE_TEXT_CORRECTIONS.items():
        corrected = corrected.replace(wrong, right)
    return corrected


def _format_amount(amount: float):
    if amount == int(amount):
        return int(amount)
    return amount


def _match_dose_line(text: str):
    """복용 정보 줄이면 (dose_amount, dose_unit, frequency_per_day, duration_days, normalized_text)를 반환, 아니면 None."""
    corrected = _apply_dose_corrections(text)
    match = DOSE_PATTERN.search(corrected)
    if not match:
        return None

    raw_amount, unit, freq, duration = match.groups()
    amount = _format_amount(float(raw_amount))
    frequency_per_day = int(freq)
    duration_days = int(duration)
    normalized_text = f"{amount}{unit}씩 {frequency_per_day}회 {duration_days}일분"

    return {
        "dose_amount": amount,
        "dose_unit": unit,
        "frequency_per_day": frequency_per_day,
        "duration_days": duration_days,
        "normalized_text": normalized_text,
    }


def _is_excluded_line(text: str) -> bool:
    return any(bad in text for bad in EXCLUDED_NAME_SUBSTRINGS)


def _is_medicine_name_candidate(text: str) -> bool:
    if _is_excluded_line(text):
        return False
    if not text.strip():
        return False
    return any(keyword in text for keyword in MEDICINE_NAME_KEYWORDS)


def parse_medicines_from_ocr_lines(ocr_lines):
    """OCR 라인 리스트(텍스트, 신뢰도)에서 약 정보 리스트를 추출한다."""
    dose_candidates = []  # (index, dose_info, confidence)
    name_candidates = []  # (index, text, confidence)

    for index, (text, confidence) in enumerate(ocr_lines):
        text = text.strip()
        if not text or _is_excluded_line(text):
            continue

        dose_info = _match_dose_line(text)
        if dose_info is not None:
            dose_candidates.append((index, dose_info, confidence))
            continue

        if _is_medicine_name_candidate(text):
            name_candidates.append((index, text, confidence))

    medicines = []
    used_dose_indices = set()

    for name_index, name_text, name_confidence in name_candidates:
        matched_dose = None
        matched_dose_confidence = None

        for dose_index, dose_info, dose_confidence in dose_candidates:
            if dose_index in used_dose_indices:
                continue
            if dose_index <= name_index:
                continue
            matched_dose = dose_info
            matched_dose_confidence = dose_confidence
            used_dose_indices.add(dose_index)
            break

        if matched_dose is not None:
            confidence = round((name_confidence + matched_dose_confidence) / 2, 2)
            medicines.append(
                {
                    "medicine_name": name_text,
                    "category": matched_dose,
                    "confidence": confidence,
                    "needs_user_confirmation": True,
                    "uncertain": False,
                    "uncertainty_note": "",
                }
            )
        else:
            medicines.append(
                {
                    "medicine_name": name_text,
                    "category": {
                        "dose_amount": None,
                        "dose_unit": None,
                        "frequency_per_day": None,
                        "duration_days": None,
                        "normalized_text": "",
                    },
                    "confidence": round(name_confidence, 2),
                    "needs_user_confirmation": True,
                    "uncertain": True,
                    "uncertainty_note": "복용 정보를 찾지 못했습니다.",
                }
            )

    return medicines


def analyze_medicine_image(image_path: str):
    """이미지 경로를 받아 OCR을 수행하고 약 정보 리스트를 반환한다."""
    ocr_lines = extract_ocr_lines(image_path)
    return parse_medicines_from_ocr_lines(ocr_lines)
