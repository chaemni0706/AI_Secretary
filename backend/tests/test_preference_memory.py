"""memory_service — 발화 기반 Preference 추출/저장/조회 테스트.

- 허용목록/블록리스트 검증(_validate_pref)
- LLM 추출(extract_preference) 매핑 (generate_json monkeypatch)
- 저장→조회 라운드트립 + 추천 프로필 매핑 (임시 DB)
- 플래그 OFF / 민감정보 차단
실제 OpenAI 호출은 monkeypatch 로 대체한다.
"""

import pytest
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine
from backend.services import memory_service as M

U = "local-user"


@pytest.fixture()
def db(tmp_path):
    db_file = tmp_path / "mem.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# 허용목록 / 블록리스트
# --------------------------------------------------------------------------- #
def test_validate_accepts_enum():
    assert M._validate_pref("preferred_focus_time", "afternoon") == {
        "key": "preferred_focus_time", "value": "afternoon"}
    assert M._validate_pref("assistant_tone", "Friendly") == {
        "key": "assistant_tone", "value": "friendly"}  # 소문자 정규화


def test_validate_rejects_unknown_key_or_value():
    assert M._validate_pref("weight_kg", "70") is None          # 허용 키 아님
    assert M._validate_pref("preferred_focus_time", "dawn") is None  # 허용 값 아님


def test_validate_rejects_sensitive():
    # repeat_habit 은 자유 토큰이지만 민감어는 차단
    assert M._validate_pref("repeat_habit", "매일 혈압약 복용") is None
    assert M._validate_pref("repeat_habit", "아침 운동") == {
        "key": "repeat_habit", "value": "아침 운동"}


def test_validate_repeat_habit_length():
    assert M._validate_pref("repeat_habit", "가" * 30) is None  # 20자 초과


# --------------------------------------------------------------------------- #
# LLM 추출 매핑 (generate_json monkeypatch)
# --------------------------------------------------------------------------- #
def test_extract_preference_valid(monkeypatch):
    monkeypatch.setattr(M.llm_service, "generate_json",
                        lambda *a, **k: {"type": "preference",
                                         "key": "preferred_focus_time", "value": "afternoon"})
    assert M.extract_preference("나는 아침엔 집중이 잘 안돼") == {
        "key": "preferred_focus_time", "value": "afternoon"}


def test_extract_preference_type_none(monkeypatch):
    monkeypatch.setattr(M.llm_service, "generate_json", lambda *a, **k: {"type": "none"})
    assert M.extract_preference("오늘 날씨 좋다") is None


def test_extract_preference_sensitive_blocked(monkeypatch):
    # LLM이 실수로 민감정보를 담아도 검증에서 폐기
    monkeypatch.setattr(M.llm_service, "generate_json",
                        lambda *a, **k: {"type": "preference",
                                         "key": "repeat_habit", "value": "우울증 약 복용"})
    assert M.extract_preference("...") is None


# --------------------------------------------------------------------------- #
# 저장 → 조회 → 추천 프로필 매핑 (DB)
# --------------------------------------------------------------------------- #
def test_save_get_and_profile(db, monkeypatch):
    monkeypatch.setattr(M.settings, "ENABLE_LLM_MEMORY", True)
    monkeypatch.setattr(M.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(M.llm_service, "generate_json",
                        lambda *a, **k: {"type": "preference",
                                         "key": "preferred_focus_time", "value": "afternoon"})

    saved = M.extract_and_save_preference(db, U, "나는 아침엔 집중이 잘 안돼")
    assert saved == {"key": "preferred_focus_time", "value": "afternoon"}

    # 조회
    assert M.get_learned_preferences(db, U)["preferred_focus_time"] == "afternoon"

    # 추천 활용: reschedule user_profile 형태로 매핑
    profile = M.build_recommendation_profile(db, U)
    assert profile["preferred_time_blocks"] == ["afternoon"]


def test_flag_off_saves_nothing(db, monkeypatch):
    monkeypatch.setattr(M.settings, "ENABLE_LLM_MEMORY", False)
    called = {"n": 0}
    monkeypatch.setattr(M, "extract_preference", lambda t: called.__setitem__("n", 1))
    assert M.extract_and_save_preference(db, U, "나는 아침엔 집중이 잘 안돼") is None
    assert called["n"] == 0
    assert M.get_learned_preferences(db, U) == {}
