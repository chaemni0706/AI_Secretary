"""M1/M3 서비스용 LR Pipeline 공통 정의.

학습(train_production_models.py)과 서비스(ml_recommender.py)가 같은 클래스를
import해야 joblib.load()가 역직렬화에 성공한다 (pickle은 클래스를 모듈 경로로 찾음).
data/models/model_m{1,3}_lr.joblib에는 클래스가 최상위 모듈 경로
(ml_pipeline_common.DerivedFeatures)로 기록되어 있으므로, 로딩하는 쪽에서
sys.modules["ml_pipeline_common"]에 이 모듈을 등록한 뒤 joblib.load()를
호출해야 한다 (ml_recommender.py가 수행).

전처리 방식은 train_ml_models.py(GroupKFold 검증용)와 동일한 구성을 따른다:
  - 응답자 성향 5개 + gender_male + age_ord + job_group 원핫
  - 후보 수치형 그대로 + 후보 범주형 원핫
  - 위 전체를 StandardScaler로 표준화(원핫 더미 포함, train_ml_models.py와 동일)
차이점은 pd.get_dummies를 OneHotEncoder(handle_unknown="ignore")로 바꾼 것뿐이다.
학습 데이터에 없던 범주가 서비스 단계에서 들어와도 에러 없이 0벡터로 처리되도록 하기 위함.
"""
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TRAIT_COLS = ["planning_score", "execution_score", "morning_score", "social_score", "exploration_score"]
AGE_ORD = {"10대": 1, "20대": 2, "30대": 3, "40대": 4, "50대": 5}

# 모델별로 서비스가 candidate dict에 넣어줘야 하는 원본 키 (variable_dictionary.md 이름 그대로).
# duration_minutes(M1)는 여기 없음 — start_time/end_time으로부터 파이프라인 내부에서 계산됨.
RAW_CAND_COLS = {
    "M1": ["candidate_id", "start_time", "end_time", "day_index", "start_minutes",
           "week_start_minutes", "time_slot", "is_weekend", "is_earliest_free_slot",
           "day_event_count", "before_free_minutes", "after_free_minutes",
           "is_empty_day", "is_right_after_existing_event"],
    "M3": ["candidate_id", "place_category", "distance_minutes", "distance_km",
           "price_level", "wait_minutes", "rating", "review_count",
           "reservation_available", "atmosphere", "purpose_fit_level", "familiarity_level"],
}

# user dict에 필요한 키 (M1/M3 공통)
USER_RAW_COLS = ["gender", "age_group", "job_group", *TRAIT_COLS]

CAND_NUM = {
    "M1": ["day_index", "start_minutes", "week_start_minutes", "duration_minutes",
           "is_weekend", "is_earliest_free_slot", "day_event_count",
           "before_free_minutes", "after_free_minutes", "is_empty_day",
           "is_right_after_existing_event"],
    "M3": ["distance_minutes", "distance_km", "price_level", "wait_minutes",
           "rating", "review_count", "reservation_available",
           "purpose_fit_level", "familiarity_level"],
}
CAND_CAT = {
    "M1": ["time_slot"],
    "M3": ["place_category", "atmosphere"],
}
USER_NUM = [*TRAIT_COLS, "gender_male", "age_ord"]
USER_CAT = ["job_group"]


def hhmm_to_min(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


class DerivedFeatures(BaseEstimator, TransformerMixin):
    """원본 입력(HH:MM 문자열, gender/age_group 문자열)에서 모델이 쓰는 파생 컬럼을 만든다.
    Pipeline의 첫 단계로 들어가므로, 이 단계 밖에서 미리 계산해 넣을 필요가 없다.
    """

    def __init__(self, model_key):
        self.model_key = model_key

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        if self.model_key == "M1":
            X["duration_minutes"] = (
                X["end_time"].map(hhmm_to_min) - X["start_time"].map(hhmm_to_min)
            )
        X["gender_male"] = (X["gender"] == "남").astype(int)
        X["age_ord"] = X["age_group"].map(AGE_ORD)
        return X


def build_pipeline(model_key, seed=42):
    """model_key: "M1" 또는 "M3". 전처리(파생컬럼 생성+원핫+표준화)+LogisticRegression Pipeline."""
    num_cols = USER_NUM + CAND_NUM[model_key]
    cat_cols = USER_CAT + CAND_CAT[model_key]
    pre = ColumnTransformer([
        ("num", "passthrough", num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])
    return Pipeline([
        ("derive", DerivedFeatures(model_key)),
        ("prep", pre),
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(max_iter=2000, random_state=seed)),
    ])
