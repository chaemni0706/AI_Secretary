"""개인화 추천 서비스 — M1(빈 시간)·M3(장소)는 ML, M2(미룰 일정)는 규칙 기반.

M1·M3는 data/models/model_m{1,3}_lr.joblib에 저장된 sklearn Pipeline
(전처리+LogisticRegression, ml_pipeline_common.build_pipeline이 생성)을 로드해서 쓴다.
Pipeline이 원본 값(HH:MM 문자열, 카테고리 문자열)을 그대로 받아 내부에서 전부 변환하므로,
호출하는 쪽에서 별도 인코딩/스케일링을 할 필요가 없다.

M2(미룰 일정)는 ML로 채택되지 않아 모델 파일이 없다 — reschedule_recommender와 같은
rules/ 컨벤션(가중 선형 합, 0..1 정규화)을 따르는 rules/postpone_rules.json 기반
스코어링을 쓴다.

candidate/user dict의 키는 모두 variable_dictionary.md의 변수명을 그대로 쓴다.

Public API (모두 user dict + candidates list[dict]를 받아
[{"candidate_id": str, "score": float}] 상위 3개를 score 내림차순으로 반환):
    recommend_free_time(user, candidates)  # M1
    recommend_postpone(user, candidates)   # M2
    recommend_place(user, candidates)      # M3
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import joblib
import pandas as pd

from backend.services import ml_pipeline_common

# joblib 파일에는 DerivedFeatures가 최상위 모듈 경로(ml_pipeline_common.DerivedFeatures)로
# 기록되어 있어, 같은 이름의 모듈이 없으면 역직렬화가 ModuleNotFoundError로 실패한다.
sys.modules.setdefault("ml_pipeline_common", ml_pipeline_common)

_MODEL_DIR = Path(__file__).resolve().parents[1] / "data" / "models"
_POSTPONE_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "postpone_rules.json"


@lru_cache(maxsize=None)
def _load_pipeline(filename: str):
    return joblib.load(_MODEL_DIR / filename)


@lru_cache(maxsize=1)
def load_postpone_rules() -> dict:
    with open(_POSTPONE_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _candidates_to_df(user: dict, candidates: List[dict]) -> pd.DataFrame:
    """candidate dict 리스트 + user dict 1개 -> Pipeline 입력용 DataFrame(후보당 1행)."""
    df = pd.DataFrame(candidates)
    for key, value in user.items():
        df[key] = value
    return df


def _top3_by_score(candidate_ids: List[str], scores) -> List[Dict]:
    order = sorted(zip(candidate_ids, scores), key=lambda x: (-x[1], x[0]))
    return [{"candidate_id": cid, "score": float(s)} for cid, s in order[:3]]


def recommend_free_time(user: dict, candidates: List[dict]) -> List[Dict]:
    """M1 — 빈 시간 추천. 후보 중 상위 3개를 예측 확률 내림차순으로 반환.

    candidates: list[dict]. 각 dict에 필요한 키:
      candidate_id, start_time, end_time, day_index, start_minutes, week_start_minutes,
      time_slot, is_weekend, is_earliest_free_slot, day_event_count,
      before_free_minutes, after_free_minutes, is_empty_day, is_right_after_existing_event
      (duration_minutes는 start_time/end_time으로부터 Pipeline 내부에서 자동 계산됨)

    user: dict. 필요한 키:
      gender, age_group, job_group, planning_score, execution_score, morning_score,
      social_score, exploration_score
    """
    pipe = _load_pipeline("model_m1_lr.joblib")
    df = _candidates_to_df(user, candidates)
    proba = pipe.predict_proba(df)[:, 1]
    return _top3_by_score(df["candidate_id"].tolist(), proba)


def recommend_place(user: dict, candidates: List[dict]) -> List[Dict]:
    """M3 — 장소 추천. 후보 중 상위 3개를 예측 확률 내림차순으로 반환.

    candidates: list[dict]. 각 dict에 필요한 키:
      candidate_id, place_category, distance_minutes, distance_km, price_level,
      wait_minutes, rating, review_count, reservation_available, atmosphere,
      purpose_fit_level, familiarity_level

    user: dict. recommend_free_time과 동일 키.
    """
    pipe = _load_pipeline("model_m3_lr.joblib")
    df = _candidates_to_df(user, candidates)
    proba = pipe.predict_proba(df)[:, 1]
    return _top3_by_score(df["candidate_id"].tolist(), proba)


def _score_postpone(candidate: dict, social_score: float, rules: dict) -> float:
    """미루기 적합도 0..1. 가중치 합이 1.0이라 별도 정규화 불필요."""
    lo, hi = rules["level_min"], rules["level_max"]

    def norm(value) -> float:
        return (float(value) - lo) / (hi - lo)

    w = rules["weights"]
    # 타인과 함께하는 일정은 미루기 부담 — 사교 성향이 높을수록 감점이 커진다.
    other_people_penalty = (
        rules["social_penalty_base"] + rules["social_penalty_scale"] * norm(social_score)
    )
    raw = (
        w["reschedulability"] * norm(candidate["reschedulability_level"])
        + w["low_importance"] * (1.0 - norm(candidate["importance_level"]))
        + w["low_urgency"] * (1.0 - norm(candidate["urgency_level"]))
        + w["low_penalty_if_postponed"] * (1.0 - norm(candidate["penalty_if_postponed_level"]))
        + w["fatigue_burden"] * norm(candidate["fatigue_burden_level"])
        + w["no_other_people"]
        * (1.0 - float(candidate["has_other_people"]) * other_people_penalty)
    )
    return round(max(0.0, min(1.0, raw)), 4)


def recommend_postpone(user: dict, candidates: List[dict]) -> List[Dict]:
    """M2 — 미룰 일정 추천 (규칙 기반, rules/postpone_rules.json. 모델 파일 불필요).

    candidates: list[dict]. 각 dict에 필요한 키:
      candidate_id, reschedulability_level, importance_level, urgency_level,
      fatigue_burden_level, penalty_if_postponed_level, has_other_people

    user: dict. 필요한 키: social_score (M2는 사교형 성향만 사용함).
    """
    rules = load_postpone_rules()
    social_score = user["social_score"]
    candidate_ids = [c["candidate_id"] for c in candidates]
    scores = [_score_postpone(c, social_score, rules) for c in candidates]
    return _top3_by_score(candidate_ids, scores)
