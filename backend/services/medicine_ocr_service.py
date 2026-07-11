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
from datetime import date

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
    """이미지에서 (텍스트, 신뢰도, bbox) 튜플 리스트를 추출한다.

    bbox 는 (x_min, y_min, x_max, y_max) 이며, 좌표 정보가 없으면 None.
    """
    engine = _get_ocr_engine()
    results = engine.predict(image_path)
    if not results:
        return []

    result = results[0]
    texts = result.get("rec_texts", [])
    scores = result.get("rec_scores", [])
    boxes = result.get("rec_boxes")

    lines = []
    for i, (text, score) in enumerate(zip(texts, scores)):
        box = None
        if boxes is not None and i < len(boxes):
            x_min, y_min, x_max, y_max = boxes[i]
            box = (float(x_min), float(y_min), float(x_max), float(y_max))
        lines.append((text, score, box))
    return lines


# ---------------------------------------------------------------------------
# OCR 오인식 보정 규칙 (복용 정보 줄에만 적용)
# ---------------------------------------------------------------------------
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


def _apply_dose_corrections(text: str) -> str:
    corrected = text
    for wrong, right in DOSE_TEXT_CORRECTIONS.items():
        corrected = corrected.replace(wrong, right)
    return corrected


# ---------------------------------------------------------------------------
# 약 이름 판별
# ---------------------------------------------------------------------------
# 약 이름은 항상 이 접미사로 끝난다(약 이름 뒤에 함량이 붙는 "타이레놀정 500mg" 형태 포함).
DRUG_NAME_SUFFIXES = ("정", "캡슐", "시럽", "과립", "현탁액", "액", "mg", "g")

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

# "1정", "1캡슐" 처럼 숫자+복용형태단위만 있는 줄 (약 이름이 아니라 1회 복용량 값).
BARE_DOSE_TOKEN_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(정|캡슐|포|환|알|병)$")

# "250mg" 처럼 숫자+함량단위만 있는 줄 (약 이름이 아니라 함량 값 -> 이름에 합쳐야 함).
BARE_STRENGTH_TOKEN_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(mg|g|ml)$")

# "2회" 처럼 접두어 없이 단독으로 오는 하루 복용 횟수 (표 형식의 개별 칸).
BARE_FREQUENCY_TOKEN_PATTERN = re.compile(r"^(\d+)\s*회$")

# "3일분" 처럼 접두어 없이 단독으로 오는 복용 기간 (표 형식의 개별 칸).
BARE_DURATION_TOKEN_PATTERN = re.compile(r"^(\d+)\s*일\s*분$")

# 한 줄에 복용정보가 전부 있는 기존 패턴: "1캡슐씩 2회 4일분" 형태.
FULL_DOSE_LINE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(정|캡슐|포|병|환|알|mg|g|ml)\s*씩\s*(\d+)\s*회\s*(\d+)\s*일?\s*분?"
)

# 약품명+함량+1회복용량이 공백 없이 한 덩어리로 인식된 경우 분해한다.
# 예: "타이레놀정500mg1정" -> 이름 "타이레놀정", 함량 "500mg", 복용량 "1정".
# 표의 칸 간격이 좁으면 OCR 텍스트 검출기가 여러 칸을 한 박스로 합쳐서 인식하는
# 경우가 실제로 있어(bbox 로는 분리할 수 없음), 정규식으로 뒤쪽부터 역으로 분해한다.
COMBINED_NAME_DOSE_PATTERN = re.compile(
    r"^(.+?)(\d+(?:\.\d+)?\s*(?:mg|g|ml))?\s*(\d+(?:\.\d+)?\s*(?:정|캡슐|포|환|알|병))$"
)

# 약봉투 전체에 공통으로 적용되는 "하루 2회" / "3일분" (개별 약에 값이 없을 때 fallback).
COMMON_FREQUENCY_PATTERN = re.compile(r"(?:하루|1일)\s*(\d+)\s*회")
COMMON_DURATION_PATTERN = re.compile(r"(\d+)\s*일\s*(?:분|치)")


def _is_excluded_line(text: str) -> bool:
    return any(bad in text for bad in EXCLUDED_NAME_SUBSTRINGS)


def _is_medicine_name_line(corrected_text: str) -> bool:
    """약 이름 줄인지 판정: 접미사로 끝나야 하고, 숫자+단위 조각(bare token)이면 안 된다."""
    if BARE_DOSE_TOKEN_PATTERN.fullmatch(corrected_text) or BARE_STRENGTH_TOKEN_PATTERN.fullmatch(
        corrected_text
    ):
        return False
    return corrected_text.endswith(DRUG_NAME_SUFFIXES)


def _match_full_dose_line(corrected_text: str):
    """한 줄에 복용정보가 전부 있는 경우 (dose, frequency_per_day, duration_days) 반환, 아니면 None."""
    match = FULL_DOSE_LINE_PATTERN.search(corrected_text)
    if not match:
        return None
    raw_amount, unit, freq, duration = match.groups()
    amount = float(raw_amount)
    amount_display = int(amount) if amount == int(amount) else amount
    return {
        "dose": f"{amount_display}{unit}",
        "frequency_per_day": int(freq),
        "duration_days": int(duration),
    }


def _split_combined_name_dose(corrected_text: str):
    """"약품명+함량+1회복용량"이 한 덩어리로 인식된 줄을 분해한다.

    성공하면 (medicine_name, dose) 를 반환, 아니면 None.
    이름 부분이 약 이름 접미사로 끝나지 않으면(순수 노이즈로 오분해될 위험) 버린다.
    """
    match = COMBINED_NAME_DOSE_PATTERN.match(corrected_text)
    if not match:
        return None
    name_part, strength_part, dose_part = match.groups()
    name_part = name_part.strip()
    if not name_part or not name_part.endswith(DRUG_NAME_SUFFIXES):
        return None
    if strength_part:
        name_part = f"{name_part} {strength_part.strip()}"
    return name_part, dose_part.strip()


# ---------------------------------------------------------------------------
# bbox 기반 같은 행 정렬
# ---------------------------------------------------------------------------
def _reorder_lines_by_bbox(lines):
    """bbox 가 있으면 y좌표가 비슷한 항목을 같은 행으로 묶고, 행 안에서는 x좌표
    순서로 정렬해 재배열한다. bbox 가 없는 항목이 하나라도 있으면(좌표 정보 부족)
    원래 순서를 그대로 반환해 정규식 기반 fallback 로직이 처리하도록 둔다.
    """
    if not lines or any(box is None for _, _, box in lines):
        return lines

    def y_center(line):
        box = line[2]
        return (box[1] + box[3]) / 2

    sorted_lines = sorted(lines, key=y_center)

    rows = [[sorted_lines[0]]]
    for line in sorted_lines[1:]:
        current_row = rows[-1]
        row_centers = [y_center(l) for l in current_row]
        row_avg_center = sum(row_centers) / len(row_centers)
        row_heights = [l[2][3] - l[2][1] for l in current_row]
        height = line[2][3] - line[2][1]
        threshold = max(max(row_heights), height) * 0.6
        if abs(y_center(line) - row_avg_center) <= threshold:
            current_row.append(line)
        else:
            rows.append([line])

    reordered = []
    for row in rows:
        reordered.extend(sorted(row, key=lambda l: l[2][0]))  # x_min 순
    return reordered


# ---------------------------------------------------------------------------
# 조제일 추출
# ---------------------------------------------------------------------------
DISPENSED_LABEL = "조제일"

_YMD_DASH_PATTERN = re.compile(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})")
_YMD_KR_PATTERN = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_MD_DOT_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?!\d)")
_MD_KR_PATTERN = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")


def _extract_dispensed_date(cleaned_lines):
    """(dispensed_date: 'YYYY-MM-DD' | None, note: str) 를 반환한다.

    note 는 fallback(연도 추정 등)이 적용되었거나 추출에 실패했을 때 그 사실을
    감추지 않고 사용자에게 알리기 위한 문구다.
    """
    today = date.today()

    label_pos = None
    for pos, (_idx, original, _corrected, _conf) in enumerate(cleaned_lines):
        if DISPENSED_LABEL in original:
            label_pos = pos
            break

    if label_pos is not None:
        candidate_texts = [cleaned_lines[label_pos][2]]
        if label_pos + 1 < len(cleaned_lines):
            candidate_texts.append(cleaned_lines[label_pos + 1][2])
    else:
        # 라벨이 없으면 연도 없는(월.일) 패턴은 오탐 위험이 커서 사용하지 않는다.
        candidate_texts = [c for _idx, _o, c, _conf in cleaned_lines]

    for text in candidate_texts:
        m = _YMD_DASH_PATTERN.search(text) or _YMD_KR_PATTERN.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return date(year, month, day).isoformat(), ""
            except ValueError:
                continue

    if label_pos is not None:
        for text in candidate_texts:
            m = _MD_DOT_PATTERN.search(text) or _MD_KR_PATTERN.search(text)
            if not m:
                continue
            month, day = int(m.group(1)), int(m.group(2))
            year = today.year
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            note = f"조제일에 연도 정보가 없어 {year}년으로 추정했습니다."
            if candidate > today:
                year -= 1
                try:
                    candidate = date(year, month, day)
                except ValueError:
                    continue
                note = f"조제일에 연도 정보가 없고 추정 연도가 미래여서 {year}년으로 보정했습니다."
            return candidate.isoformat(), note

    return None, "조제일을 인식하지 못했습니다. 시작일을 직접 입력해 주세요."


# ---------------------------------------------------------------------------
# 약 정보 파싱 (표 형식: 약품명 -> 함량/1회복용량 이 뒤따르는 줄들)
# ---------------------------------------------------------------------------
def parse_medicines_from_ocr_lines(ocr_lines):
    """OCR 라인 리스트(텍스트, 신뢰도[, bbox])에서 약 목록 + 조제일을 추출한다.

    bbox 가 있으면 같은 행(표의 한 줄)으로 묶어 왼쪽->오른쪽, 위->아래 순서로
    재배열한 뒤 처리한다. bbox 가 없으면 원래 OCR 순서 그대로 정규식 기반으로
    처리한다(fallback).
    """
    normalized = []
    for item in ocr_lines:
        if len(item) == 3:
            text, confidence, box = item
        else:
            text, confidence = item
            box = None
        normalized.append((text, confidence, box))

    normalized = _reorder_lines_by_bbox(normalized)

    cleaned = []
    for idx, (text, confidence, _box) in enumerate(normalized):
        original = text.strip()
        if not original:
            continue
        cleaned.append((idx, original, _apply_dose_corrections(original), confidence))

    # 1) 약봉투 공통 정보(하루 N회 / N일분) 추출 - 이미 한 줄 완결 패턴으로 소비된 줄은 제외.
    common_frequency = None
    common_duration = None
    for _idx, original, corrected, _conf in cleaned:
        if _is_excluded_line(original) or _match_full_dose_line(corrected) is not None:
            continue
        if common_frequency is None:
            freq_match = COMMON_FREQUENCY_PATTERN.search(corrected)
            if freq_match:
                common_frequency = int(freq_match.group(1))
        if common_duration is None:
            dur_match = COMMON_DURATION_PATTERN.search(corrected)
            if dur_match:
                common_duration = int(dur_match.group(1))

    dispensed_date, dispensed_date_note = _extract_dispensed_date(cleaned)

    # 2) 약품명 줄을 기준으로 뒤따르는 함량/복용량 줄을 같은 약으로 묶는다.
    medicines = []
    current = None

    for _idx, original, corrected, _conf in cleaned:
        if _is_excluded_line(original):
            continue

        full_dose = _match_full_dose_line(corrected)
        if full_dose is not None:
            if current is not None:
                current["dose"] = full_dose["dose"]
                current["frequency_per_day"] = full_dose["frequency_per_day"]
                current["duration_days"] = full_dose["duration_days"]
            continue

        combined = _split_combined_name_dose(corrected)
        if combined is not None:
            medicine_name, dose = combined
            current = {
                "medicine_name": medicine_name,
                "dose": dose,
                "frequency_per_day": None,
                "duration_days": None,
            }
            medicines.append(current)
            continue

        if BARE_DOSE_TOKEN_PATTERN.fullmatch(corrected):
            if current is not None and current["dose"] is None:
                current["dose"] = corrected
            continue

        if BARE_STRENGTH_TOKEN_PATTERN.fullmatch(corrected):
            if current is not None and not current["medicine_name"].endswith(("mg", "g", "ml")):
                current["medicine_name"] = f"{current['medicine_name']} {corrected}"
            continue

        freq_token = BARE_FREQUENCY_TOKEN_PATTERN.fullmatch(corrected)
        if freq_token:
            if current is not None and current["frequency_per_day"] is None:
                current["frequency_per_day"] = int(freq_token.group(1))
            continue

        duration_token = BARE_DURATION_TOKEN_PATTERN.fullmatch(corrected)
        if duration_token:
            if current is not None and current["duration_days"] is None:
                current["duration_days"] = int(duration_token.group(1))
            continue

        if _is_medicine_name_line(corrected):
            current = {
                "medicine_name": original,
                "dose": None,
                "frequency_per_day": None,
                "duration_days": None,
            }
            medicines.append(current)
            continue

        # 그 외(공통 정보 줄, 안내 문구 등)는 무시한다.

    result = []
    for m in medicines:
        result.append(
            {
                "medicine_name": m["medicine_name"],
                "dose": m["dose"] or "",
                "frequency_per_day": m["frequency_per_day"] if m["frequency_per_day"] is not None else common_frequency,
                "duration_days": m["duration_days"] if m["duration_days"] is not None else common_duration,
            }
        )

    return {
        "medicines": result,
        "dispensed_date": dispensed_date,
        "dispensed_date_note": dispensed_date_note,
    }


def analyze_medicine_image(image_path: str):
    """이미지 경로를 받아 OCR을 수행하고 {medicines, dispensed_date, dispensed_date_note} 를 반환한다."""
    ocr_lines = extract_ocr_lines(image_path)
    return parse_medicines_from_ocr_lines(ocr_lines)
