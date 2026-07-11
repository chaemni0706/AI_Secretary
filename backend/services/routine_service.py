"""복약 루틴 저장/조회 서비스. 현재는 JSON 파일 기반이며, 추후 DB로 교체 가능하도록 분리되어 있다."""

import json
import os
import uuid
from datetime import date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ROUTINES_FILE = os.path.join(DATA_DIR, "medicine_routines.json")

DEFAULT_TIMES_BY_FREQUENCY = {
    1: ["09:00"],
    2: ["09:00", "18:00"],
    3: ["09:00", "13:00", "18:00"],
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
    """확인된 약 정보 리스트로부터 복약 루틴을 생성하고 JSON 파일에 저장한다.

    약 1건당 duration_days 일 동안 매일 frequency_per_day 회의 개별 복용 일정
    (schedule)을 내부적으로 생성한다. 화면에는 약 단위 요약(시작~종료일, 시간)만
    노출하면 되므로 routine 레코드에 요약 필드 + schedule 배열을 함께 저장한다.
    """
    try:
        start = date.fromisoformat(start_date)
    except ValueError as exc:
        raise ValueError(f"start_date 형식이 올바르지 않습니다 (YYYY-MM-DD 필요): {start_date}") from exc

    new_routines = []

    for medicine in medicines:
        frequency_per_day = medicine.get("frequency_per_day") or 1
        duration_days = medicine.get("duration_days") or 1
        dose = medicine.get("dose") or ""
        times = _generate_default_times(frequency_per_day)
        end = start + timedelta(days=duration_days - 1)

        schedule = [
            {"date": (start + timedelta(days=day_offset)).isoformat(), "time": t}
            for day_offset in range(duration_days)
            for t in times
        ]

        routine = {
            "routine_id": f"routine_{uuid.uuid4().hex[:12]}",
            "medicine_name": medicine.get("medicine_name", ""),
            "dose_text": f"1회 {dose}".strip() if dose else "",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "duration_days": duration_days,
            "frequency_per_day": frequency_per_day,
            "times": times,
            "status": "active",
            "schedule": schedule,
        }
        new_routines.append(routine)

    existing_routines = _load_routines()
    existing_routines.extend(new_routines)
    _save_routines(existing_routines)

    return new_routines


def get_all_routines():
    return _load_routines()
