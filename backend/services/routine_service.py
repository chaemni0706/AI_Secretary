"""복약 루틴 저장/조회 서비스. 현재는 JSON 파일 기반이며, 추후 DB로 교체 가능하도록 분리되어 있다."""

import json
import os
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ROUTINES_FILE = os.path.join(DATA_DIR, "medicine_routines.json")

DEFAULT_TIMES_BY_FREQUENCY = {
    1: ["09:00"],
    2: ["09:00", "21:00"],
    3: ["08:00", "13:00", "19:00"],
    4: ["08:00", "12:00", "18:00", "22:00"],
}


def _generate_default_times(frequency_per_day: int):
    if frequency_per_day in DEFAULT_TIMES_BY_FREQUENCY:
        return DEFAULT_TIMES_BY_FREQUENCY[frequency_per_day]

    if not frequency_per_day or frequency_per_day <= 0:
        return ["09:00"]

    interval_hours = 24 // frequency_per_day
    times = []
    for i in range(frequency_per_day):
        hour = (9 + i * interval_hours) % 24
        times.append(f"{hour:02d}:00")
    return times


def _load_routines():
    if not os.path.exists(ROUTINES_FILE):
        return []

    with open(ROUTINES_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def _save_routines(routines):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ROUTINES_FILE, "w", encoding="utf-8") as f:
        json.dump(routines, f, ensure_ascii=False, indent=2)


def create_medicine_routines(medicines, start_date: str):
    """확인된 약 정보 리스트로부터 복약 루틴을 생성하고 JSON 파일에 저장한다."""
    new_routines = []

    for medicine in medicines:
        category = medicine.get("category") or {}
        frequency_per_day = category.get("frequency_per_day") or 1
        duration_days = category.get("duration_days") or 1
        times = _generate_default_times(frequency_per_day)

        routine = {
            "routine_id": f"routine_{uuid.uuid4().hex[:12]}",
            "medicine_name": medicine.get("medicine_name", ""),
            "dose_text": category.get("normalized_text", ""),
            "start_date": start_date,
            "duration_days": duration_days,
            "times": times,
            "status": "active",
        }
        new_routines.append(routine)

    existing_routines = _load_routines()
    existing_routines.extend(new_routines)
    _save_routines(existing_routines)

    return new_routines


def get_all_routines():
    return _load_routines()
