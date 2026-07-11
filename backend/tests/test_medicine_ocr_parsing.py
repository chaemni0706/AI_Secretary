"""약봉투 OCR 파싱 로직(parse_medicines_from_ocr_lines) 단위 테스트.

실제 OCR 모델을 로드하지 않고, OCR 결과(텍스트/신뢰도[/bbox])만으로
약 이름/복용량/복용 정보 병합 로직을 검증한다.
"""

from backend.services.medicine_ocr_service import parse_medicines_from_ocr_lines


def test_separated_lines_merge_into_two_medicines():
    """약품명/함량/복용량/횟수/기간이 각각 다른 줄에 있어도 약 2건으로 묶여야 한다."""
    lines = [
        ("타이레놀정 500mg", 0.99),
        ("1정", 0.97),
        ("세프렉신캡슐", 0.98),
        ("250mg", 0.96),
        ("1캡슐", 0.97),
        ("하루 2회", 0.90),
        ("3일분", 0.90),
    ]
    result = parse_medicines_from_ocr_lines(lines)

    assert len(result["medicines"]) == 2
    names = [m["medicine_name"] for m in result["medicines"]]
    assert "타이레놀정 500mg" in names
    assert "세프렉신캡슐 250mg" in names
    for m in result["medicines"]:
        assert m["frequency_per_day"] == 2
        assert m["duration_days"] == 3


def test_bare_tokens_are_not_created_as_standalone_medicines():
    """1정/1캡슐/250mg/500mg/2회/3일분 은 절대 단독 medicine_name 이 되면 안 된다."""
    lines = [
        ("타이레놀정500mg1정", 0.9),
        ("2회", 0.99),
        ("3일분", 0.99),
        ("세프렉신캡슐250mg1캡슐", 0.9),
        ("2회", 0.99),
        ("3일분", 0.99),
    ]
    result = parse_medicines_from_ocr_lines(lines)

    assert len(result["medicines"]) == 2
    banned_names = {"1정", "1캡슐", "250mg", "500mg", "2회", "3일분"}
    for m in result["medicines"]:
        assert m["medicine_name"] not in banned_names

    assert result["medicines"][0] == {
        "medicine_name": "타이레놀정 500mg",
        "dose": "1정",
        "frequency_per_day": 2,
        "duration_days": 3,
    }
    assert result["medicines"][1] == {
        "medicine_name": "세프렉신캡슐 250mg",
        "dose": "1캡슐",
        "frequency_per_day": 2,
        "duration_days": 3,
    }


def test_bbox_reorders_shuffled_table_layout():
    """bbox 좌표가 있으면 뒤섞인 입력 순서도 행(y)/열(x) 기준으로 올바르게 재정렬해야 한다."""
    lines = [
        ("2회", 0.99, (338, 20, 391, 53)),
        ("타이레놀정 500mg", 0.99, (0, 17, 229, 56)),
        ("3일분", 0.99, (432, 19, 507, 54)),
        ("1캡슐", 0.97, (0, 102, 74, 131)),
        ("1정", 0.97, (260, 20, 303, 53)),
        ("2회", 0.99, (341, 102, 389, 131)),
        ("세프렉신캡슐 250mg", 0.98, (0, 99, 229, 133)),
        ("3일분", 0.99, (431, 100, 506, 131)),
    ]
    result = parse_medicines_from_ocr_lines(lines)

    assert len(result["medicines"]) == 2
    assert result["medicines"][0]["medicine_name"] == "타이레놀정 500mg"
    assert result["medicines"][0]["dose"] == "1정"
    assert result["medicines"][1]["medicine_name"] == "세프렉신캡슐 250mg"
    assert result["medicines"][1]["dose"] == "1캡슐"


def test_dispensed_date_extracted_with_label():
    lines = [
        ("조제일:2025-07-09", 0.95),
        ("타이레놀정 500mg", 0.99),
        ("1정씩 2회 3일분", 0.97),
    ]
    result = parse_medicines_from_ocr_lines(lines)
    assert result["dispensed_date"] == "2025-07-09"
    assert result["dispensed_date_note"] == ""


def test_dispensed_date_missing_reports_note_instead_of_silent_failure():
    lines = [
        ("타이레놀정 500mg", 0.99),
        ("1정씩 2회 3일분", 0.97),
    ]
    result = parse_medicines_from_ocr_lines(lines)
    assert result["dispensed_date"] is None
    assert result["dispensed_date_note"] != ""
