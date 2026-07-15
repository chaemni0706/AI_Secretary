"""
Synthetic/mock selection log dataset and Logistic Regression demo
for an AI schedule assistant reschedule-candidate recommendation feature.

IMPORTANT
---------
- This script creates a synthetic/mock dataset for presentation and demo purposes only.
- Do NOT describe this dataset as real user data.
- Unit of analysis is one candidate time slot, not one reschedule request.
- Each request_id has exactly four candidate rows and exactly one selected=1 row.
- Final model is Logistic Regression only.
- RandomForest, XGBoost, Learning-to-Rank, and conditional logit are intentionally not used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_SEED = 42
N_USERS = 40
N_REQUESTS = 400
N_CANDIDATES_PER_REQUEST = 4

# Save every output next to this .py file.
OUTPUT_DIR = Path(__file__).resolve().parent
DATASET_PATH = OUTPUT_DIR / "reschedule_candidate_mock_dataset.csv"
DICTIONARY_PATH = OUTPUT_DIR / "reschedule_candidate_data_dictionary.csv"
SCORED_TEST_PATH = OUTPUT_DIR / "reschedule_candidate_scored_test_predictions.csv"
DEMO_INPUT_PATH = OUTPUT_DIR / "reschedule_demo_candidate_input.csv"
DEMO_SCORED_PATH = OUTPUT_DIR / "reschedule_demo_candidate_scored_predictions.csv"
MODEL_PATH = OUTPUT_DIR / "reschedule_logistic_model.joblib"
METRICS_PATH = OUTPUT_DIR / "reschedule_model_metrics.json"

rng = np.random.default_rng(RANDOM_SEED)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVENT_CATEGORIES = [
    "study",
    "exercise",
    "chore",
    "shopping",
    "personal_task",
    "hospital",
    "meeting",
]
EVENT_DURATION_CHOICES = [30, 45, 60, 90, 120]
TIME_BLOCKS = ["morning", "afternoon", "evening", "night"]


def candidate_time_block(hour: int) -> str:
    if 7 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 20:
        return "evening"
    return "night"


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exp_values = np.exp(shifted)
    return exp_values / exp_values.sum()


def make_user_profiles() -> Dict[str, Dict[str, str]]:
    """Create simple mock user profiles used only for synthetic data generation."""
    users = {}
    preferred_blocks = rng.choice(
        TIME_BLOCKS,
        size=N_USERS,
        p=[0.28, 0.32, 0.30, 0.10],
    )
    for idx in range(1, N_USERS + 1):
        user_id = f"U{idx:03d}"
        users[user_id] = {"preferred_time_block": str(preferred_blocks[idx - 1])}
    return users


def choose_flexibility(event_category: str) -> str:
    """Flexible schedules appear more often, while hospital/meeting are partly fixed."""
    if event_category == "hospital":
        return str(rng.choice(["fixed", "semi_flexible", "flexible"], p=[0.55, 0.35, 0.10]))
    if event_category == "meeting":
        return str(rng.choice(["fixed", "semi_flexible", "flexible"], p=[0.45, 0.40, 0.15]))
    if event_category in ["study", "personal_task", "chore"]:
        return str(rng.choice(["fixed", "semi_flexible", "flexible"], p=[0.08, 0.26, 0.66]))
    return str(rng.choice(["fixed", "semi_flexible", "flexible"], p=[0.12, 0.33, 0.55]))


def choose_duration(event_category: str) -> int:
    if event_category in ["hospital", "chore", "shopping"]:
        return int(rng.choice(EVENT_DURATION_CHOICES, p=[0.25, 0.25, 0.30, 0.15, 0.05]))
    if event_category in ["study", "meeting"]:
        return int(rng.choice(EVENT_DURATION_CHOICES, p=[0.08, 0.12, 0.38, 0.27, 0.15]))
    return int(rng.choice(EVENT_DURATION_CHOICES, p=[0.15, 0.20, 0.35, 0.20, 0.10]))


def choose_emotion_flags(event_category: str) -> Dict[str, int]:
    """Emotion flags represent keyword detection from user utterances, not direct check-in scores."""
    base_tired = 0.18 + (0.04 if event_category in ["study", "exercise"] else 0.0)
    base_stressed = 0.16 + (0.08 if event_category in ["study", "meeting"] else 0.0)
    base_overwhelmed = 0.12 + (0.05 if event_category in ["study", "personal_task"] else 0.0)
    base_anxious = 0.11 + (0.05 if event_category in ["hospital", "meeting"] else 0.0)
    base_sad = 0.07

    tired = int(rng.random() < base_tired)
    stressed = int(rng.random() < base_stressed)
    overwhelmed = int(rng.random() < base_overwhelmed)
    anxious = int(rng.random() < base_anxious)
    sad = int(rng.random() < base_sad)
    any_emotion = tired or stressed or overwhelmed or anxious or sad
    intensity_word = int(any_emotion and rng.random() < 0.38)
    wants_reschedule = int(rng.random() < 0.96)

    return {
        "tired": tired,
        "stressed": stressed,
        "overwhelmed": overwhelmed,
        "anxious": anxious,
        "sad": sad,
        "intensity_word": intensity_word,
        "wants_reschedule": wants_reschedule,
    }


def compute_schedule_load(num_events_same_day: int, min_adjacent_gap_min: int, is_back_to_back: int) -> float:
    event_load = num_events_same_day / 8.0
    gap_pressure = 1.0 - min(min_adjacent_gap_min, 180) / 180.0
    raw = 0.58 * event_load + 0.34 * gap_pressure + 0.08 * is_back_to_back
    noisy = raw + rng.normal(0, 0.04)
    return round(clamp(noisy, 0.0, 1.0), 3)


def generate_one_request(
    request_idx: int,
    user_profiles: Dict[str, Dict[str, str]],
) -> List[Dict[str, object]]:
    user_id = str(rng.choice(list(user_profiles.keys())))
    preferred_time_block = user_profiles[user_id]["preferred_time_block"]
    request_id = f"R{request_idx:04d}"

    event_category = str(
        rng.choice(
            EVENT_CATEGORIES,
            p=[0.23, 0.11, 0.13, 0.10, 0.19, 0.07, 0.17],
        )
    )
    event_flexibility_type = choose_flexibility(event_category)
    event_duration_min = choose_duration(event_category)

    has_deadline_prob = {
        "study": 0.62,
        "personal_task": 0.42,
        "chore": 0.33,
        "shopping": 0.12,
        "exercise": 0.08,
        "hospital": 0.18,
        "meeting": 0.24,
    }[event_category]
    has_deadline = int(rng.random() < has_deadline_prob)
    hours_until_deadline = int(rng.integers(8, 121)) if has_deadline else -1

    flags = choose_emotion_flags(event_category)
    base_day_idx = int(rng.integers(0, 7))
    current_hour = int(rng.integers(8, 20))
    has_location = int(rng.random() < (0.72 if event_category in ["hospital", "meeting", "shopping", "exercise"] else 0.42))

    rows = []
    utilities = []

    for candidate_idx in range(1, N_CANDIDATES_PER_REQUEST + 1):
        candidate_id = f"C{candidate_idx}"
        days_delayed = int(rng.integers(0, 6))
        candidate_day_idx = (base_day_idx + days_delayed) % 7
        candidate_dayofweek = DAYS[candidate_day_idx]
        is_weekend = int(candidate_dayofweek in ["Sat", "Sun"])

        # Generate candidate hour with a realistic bias toward the user's preferred block.
        if rng.random() < 0.45:
            if preferred_time_block == "morning":
                candidate_hour = int(rng.integers(7, 12))
            elif preferred_time_block == "afternoon":
                candidate_hour = int(rng.integers(12, 17))
            elif preferred_time_block == "evening":
                candidate_hour = int(rng.integers(17, 21))
            else:
                candidate_hour = int(rng.integers(21, 24))
        else:
            candidate_hour = int(rng.integers(7, 24))

        block = candidate_time_block(candidate_hour)
        preferred_hour_match = int(block == preferred_time_block)

        max_margin = max(0, 180 - event_duration_min)
        margin_choices = np.array([0, 15, 30, 45, 60, 90, 120, 150])
        valid_margins = margin_choices[margin_choices <= max_margin]
        extra_time_margin_min = int(rng.choice(valid_margins, p=None))
        candidate_slot_length_min = event_duration_min + extra_time_margin_min

        # More events usually means smaller adjacent gaps.
        num_events_same_day = int(rng.choice(np.arange(0, 9), p=[0.07, 0.10, 0.14, 0.17, 0.17, 0.14, 0.10, 0.07, 0.04]))
        gap_center = max(20, 170 - num_events_same_day * 15)
        gap_before_min = int(clamp(rng.normal(gap_center, 55), 0, 240))
        gap_after_min = int(clamp(rng.normal(gap_center, 55), 0, 240))
        min_adjacent_gap_min = int(min(gap_before_min, gap_after_min))
        is_back_to_back = int(min_adjacent_gap_min <= 15)
        schedule_load_score = compute_schedule_load(num_events_same_day, min_adjacent_gap_min, is_back_to_back)

        if has_location:
            travel_time_from_prev_min = int(rng.integers(0, 91))
            travel_time_to_next_min = int(rng.integers(0, 91))
            has_travel_buffer = int(
                (gap_before_min >= travel_time_from_prev_min + 10)
                and (gap_after_min >= travel_time_to_next_min + 10)
            )
        else:
            travel_time_from_prev_min = 0
            travel_time_to_next_min = 0
            has_travel_buffer = 1

        relative_hours_to_candidate = days_delayed * 24 + max(candidate_hour - current_hour, 0)
        is_after_deadline = int(has_deadline == 1 and relative_hours_to_candidate > hours_until_deadline)

        # Latent utility is used only to generate selected. It is NOT saved as a data column.
        intensity_multiplier = 1.35 if flags["intensity_word"] else 1.0
        utility = rng.normal(0.0, 0.35)
        utility += 1.15 * preferred_hour_match
        utility += 0.35 * (extra_time_margin_min / 60.0)
        utility += 0.42 * min(min_adjacent_gap_min, 180) / 60.0
        utility -= 1.05 * is_back_to_back
        utility -= 1.35 * schedule_load_score
        utility -= 1.15 * (1 - has_travel_buffer)

        if event_flexibility_type == "fixed":
            utility -= 0.20 * days_delayed
            utility -= 0.30 if event_category in ["hospital", "meeting"] and days_delayed >= 4 else 0.0
        elif event_flexibility_type == "flexible":
            utility += 0.15

        if candidate_hour >= 22:
            utility -= 0.95
            if preferred_time_block == "night":
                utility += 0.75

        if flags["tired"]:
            utility -= intensity_multiplier * (1.15 if block == "night" else 0.0)
            utility += intensity_multiplier * (0.62 if days_delayed >= 1 and block in ["morning", "afternoon"] else 0.0)

        if flags["stressed"]:
            utility -= intensity_multiplier * (0.65 if extra_time_margin_min < 30 else 0.0)
            utility -= intensity_multiplier * (0.78 if schedule_load_score > 0.62 else 0.0)
            utility -= intensity_multiplier * (0.42 if min_adjacent_gap_min < 45 else 0.0)

        if flags["overwhelmed"]:
            utility += intensity_multiplier * (0.75 * min(min_adjacent_gap_min, 180) / 180.0)
            utility -= intensity_multiplier * (0.38 if schedule_load_score > 0.70 else 0.0)

        if flags["anxious"] and has_deadline:
            deadline_pressure = relative_hours_to_candidate / max(hours_until_deadline, 1)
            utility -= intensity_multiplier * (0.85 if deadline_pressure > 0.82 else 0.0)
            utility -= intensity_multiplier * (0.65 if hours_until_deadline <= 24 and days_delayed >= 1 else 0.0)

        if flags["sad"]:
            utility -= 0.38 if candidate_hour >= 22 else 0.0
            utility -= 0.42 if is_back_to_back else 0.0
            utility += 0.34 if min_adjacent_gap_min >= 60 else 0.0

        if is_after_deadline:
            utility -= 4.2

        row = {
            "user_id": user_id,
            "request_id": request_id,
            "candidate_id": candidate_id,
            "event_category": event_category,
            "event_flexibility_type": event_flexibility_type,
            "event_duration_min": event_duration_min,
            "has_deadline": has_deadline,
            "hours_until_deadline": hours_until_deadline,
            "is_after_deadline": is_after_deadline,
            "candidate_hour": candidate_hour,
            "candidate_dayofweek": candidate_dayofweek,
            "is_weekend": is_weekend,
            "days_delayed": days_delayed,
            "candidate_slot_length_min": candidate_slot_length_min,
            "extra_time_margin_min": extra_time_margin_min,
            "gap_before_min": gap_before_min,
            "gap_after_min": gap_after_min,
            "min_adjacent_gap_min": min_adjacent_gap_min,
            "is_back_to_back": is_back_to_back,
            "num_events_same_day": num_events_same_day,
            "schedule_load_score": schedule_load_score,
            "tired": flags["tired"],
            "stressed": flags["stressed"],
            "overwhelmed": flags["overwhelmed"],
            "anxious": flags["anxious"],
            "sad": flags["sad"],
            "intensity_word": flags["intensity_word"],
            "wants_reschedule": flags["wants_reschedule"],
            "preferred_time_block": preferred_time_block,
            "candidate_time_block": block,
            "preferred_hour_match": preferred_hour_match,
            "has_location": has_location,
            "travel_time_from_prev_min": travel_time_from_prev_min,
            "travel_time_to_next_min": travel_time_to_next_min,
            "has_travel_buffer": has_travel_buffer,
        }
        rows.append(row)
        utilities.append(utility)

    probabilities = softmax(np.array(utilities))
    selected_idx = int(rng.choice(np.arange(N_CANDIDATES_PER_REQUEST), p=probabilities))
    for idx, row in enumerate(rows):
        row["selected"] = int(idx == selected_idx)
    return rows


def generate_dataset() -> pd.DataFrame:
    user_profiles = make_user_profiles()
    all_rows: List[Dict[str, object]] = []
    for request_idx in range(1, N_REQUESTS + 1):
        all_rows.extend(generate_one_request(request_idx, user_profiles))
    df = pd.DataFrame(all_rows)
    return df


def validate_dataset(df: pd.DataFrame, has_selected: bool = True) -> None:
    assert len(df) == N_REQUESTS * N_CANDIDATES_PER_REQUEST, "row count must be 1,600"
    assert df["request_id"].nunique() == N_REQUESTS, "request count must be 400"
    assert df["user_id"].nunique() == N_USERS, "user count must be 40"
    counts = df.groupby("request_id").size()
    assert (counts == N_CANDIDATES_PER_REQUEST).all(), "each request_id must have exactly four candidates"
    if has_selected:
        selected_sum = df.groupby("request_id")["selected"].sum()
        assert (selected_sum == 1).all(), "each request_id must have exactly one selected=1 row"
    assert set(df["candidate_id"].unique()).issubset({"C1", "C2", "C3", "C4"})
    assert df["candidate_hour"].between(7, 23).all()
    assert df["candidate_slot_length_min"].between(30, 180).all()
    assert (df["extra_time_margin_min"] == df["candidate_slot_length_min"] - df["event_duration_min"]).all()
    assert (df["min_adjacent_gap_min"] == df[["gap_before_min", "gap_after_min"]].min(axis=1)).all()


def build_data_dictionary() -> pd.DataFrame:
    rows = [
        ("user_id", "string", "Mock user identifier from U001 to U040.", "U001"),
        ("request_id", "string", "Mock reschedule request identifier from R0001 to R0400.", "R0001"),
        ("candidate_id", "string", "Candidate identifier within each request; C1 to C4.", "C1"),
        ("event_category", "categorical", "Event category: study, exercise, chore, shopping, personal_task, hospital, meeting.", "study"),
        ("event_flexibility_type", "categorical", "How adjustable the event is: fixed, semi_flexible, flexible.", "flexible"),
        ("event_duration_min", "integer", "Event duration in minutes: 30, 45, 60, 90, or 120.", "60"),
        ("has_deadline", "binary", "Whether the event has a deadline.", "1"),
        ("hours_until_deadline", "integer", "Positive hours until deadline if has_deadline=1; otherwise -1.", "48"),
        ("is_after_deadline", "binary", "Whether the candidate time is after the deadline.", "0"),
        ("candidate_hour", "integer", "Candidate start hour from 7 to 23.", "14"),
        ("candidate_dayofweek", "categorical", "Candidate day of week: Mon, Tue, Wed, Thu, Fri, Sat, Sun.", "Thu"),
        ("is_weekend", "binary", "1 if candidate_dayofweek is Sat or Sun.", "0"),
        ("days_delayed", "integer", "Number of days the event is delayed, from 0 to 5.", "2"),
        ("candidate_slot_length_min", "integer", "Available candidate slot length in minutes, from 30 to 180.", "90"),
        ("extra_time_margin_min", "integer", "candidate_slot_length_min minus event_duration_min.", "30"),
        ("gap_before_min", "integer", "Free time gap before this candidate, from 0 to 240 minutes.", "75"),
        ("gap_after_min", "integer", "Free time gap after this candidate, from 0 to 240 minutes.", "90"),
        ("min_adjacent_gap_min", "integer", "Minimum of gap_before_min and gap_after_min.", "75"),
        ("is_back_to_back", "binary", "1 if either adjacent gap is 15 minutes or less.", "0"),
        ("num_events_same_day", "integer", "Number of other events on the same day, from 0 to 8.", "3"),
        ("schedule_load_score", "float", "Schedule density score from 0 to 1; higher when many events and small gaps exist.", "0.42"),
        ("tired", "binary", "Detected tired/sleepy expression from user utterance.", "1"),
        ("stressed", "binary", "Detected stress/pressure expression from user utterance.", "0"),
        ("overwhelmed", "binary", "Detected overload/too-many-schedules expression from user utterance.", "0"),
        ("anxious", "binary", "Detected anxiety/worry expression from user utterance.", "0"),
        ("sad", "binary", "Detected sadness/low mood expression from user utterance.", "0"),
        ("intensity_word", "binary", "Detected intensifier such as too, really, completely, cannot do it.", "1"),
        ("wants_reschedule", "binary", "Detected reschedule intent; mostly 1 in this mock selection log.", "1"),
        ("preferred_time_block", "categorical", "Mock user preferred time block: morning, afternoon, evening, night.", "afternoon"),
        ("candidate_time_block", "categorical", "Candidate time block derived from candidate_hour.", "afternoon"),
        ("preferred_hour_match", "binary", "1 if candidate_time_block equals preferred_time_block.", "1"),
        ("has_location", "binary", "Whether this candidate involves a location/travel consideration.", "1"),
        ("travel_time_from_prev_min", "integer", "Travel time from previous schedule, from 0 to 90 minutes.", "20"),
        ("travel_time_to_next_min", "integer", "Travel time to next schedule, from 0 to 90 minutes.", "15"),
        ("has_travel_buffer", "binary", "1 if adjacent gaps are sufficient for travel buffers.", "1"),
        ("selected", "binary", "Target variable: 1 if user selected this candidate, otherwise 0.", "1"),
    ]
    return pd.DataFrame(rows, columns=["column_name", "data_type", "description", "example_value"])


def request_group_train_test_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_SEED)
    groups = df["request_id"]
    train_idx, test_idx = next(splitter.split(df, df["selected"], groups=groups))
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()

    overlap = set(train_df["request_id"]).intersection(set(test_df["request_id"]))
    assert len(overlap) == 0, "request_id leakage: train and test share requests"
    assert (train_df.groupby("request_id")["selected"].sum() == 1).all()
    assert (test_df.groupby("request_id")["selected"].sum() == 1).all()
    return train_df, test_df


def evaluate_group_ranking(scored_df: pd.DataFrame, prob_col: str = "pred_proba") -> Dict[str, float]:
    top1_hits = []
    reciprocal_ranks = []
    for _, group in scored_df.groupby("request_id"):
        ranked = group.sort_values(prob_col, ascending=False).reset_index(drop=True)
        top1_hits.append(int(ranked.loc[0, "selected"] == 1))
        selected_rank = int(ranked.index[ranked["selected"] == 1][0]) + 1
        reciprocal_ranks.append(1.0 / selected_rank)
    return {
        "top1_accuracy": float(np.mean(top1_hits)),
        "mrr": float(np.mean(reciprocal_ranks)),
    }


def build_model(feature_cols: List[str]) -> Tuple[Pipeline, List[str], List[str]]:
    categorical_features = [
        "user_id",
        "event_category",
        "event_flexibility_type",
        "candidate_dayofweek",
        "preferred_time_block",
        "candidate_time_block",
    ]
    categorical_features = [col for col in categorical_features if col in feature_cols]
    numeric_features = [col for col in feature_cols if col not in categorical_features]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", StandardScaler(), numeric_features),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            (
                "logreg",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )
    return model, categorical_features, numeric_features


def train_evaluate_and_save(df: pd.DataFrame) -> Tuple[Pipeline, List[str], Dict[str, float]]:
    train_df, test_df = request_group_train_test_split(df)

    target = "selected"
    id_features_to_exclude = ["request_id", "candidate_id"]
    feature_cols = [col for col in df.columns if col not in [target, *id_features_to_exclude]]

    model, categorical_features, numeric_features = build_model(feature_cols)

    X_train = train_df[feature_cols]
    y_train = train_df[target]
    X_test = test_df[feature_cols]
    y_test = test_df[target]

    model.fit(X_train, y_train)
    pred_proba = model.predict_proba(X_test)[:, 1]

    scored_test = test_df.copy()
    scored_test["pred_proba"] = pred_proba
    scored_test["score"] = (scored_test["pred_proba"] * 100).round(2)
    scored_test["rank"] = scored_test.groupby("request_id")["score"].rank(method="first", ascending=False).astype(int)
    scored_test = scored_test.sort_values(["request_id", "rank"])
    scored_test.to_csv(SCORED_TEST_PATH, index=False, encoding="utf-8-sig")

    ranking_metrics = evaluate_group_ranking(scored_test, prob_col="pred_proba")
    metrics = {
        "dataset_type": "synthetic/mock selection log for presentation/demo only",
        "model": "LogisticRegression",
        "auc": round(float(roc_auc_score(y_test, pred_proba)), 4),
        "log_loss": round(float(log_loss(y_test, pred_proba)), 4),
        "top1_accuracy": round(float(ranking_metrics["top1_accuracy"]), 4),
        "mrr": round(float(ranking_metrics["mrr"]), 4),
        "train_requests": int(train_df["request_id"].nunique()),
        "test_requests": int(test_df["request_id"].nunique()),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
    }

    model_bundle = {
        "pipeline": model,
        "feature_cols": feature_cols,
        "categorical_features": categorical_features,
        "numeric_features": numeric_features,
        "note": "Synthetic/mock selection log only. Not real user data.",
    }
    joblib.dump(model_bundle, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    return model, feature_cols, metrics


def make_demo_candidate_input() -> pd.DataFrame:
    """Create three new mock reschedule requests for live demo prediction. No selected column."""
    demo_rows = [
        # DEMO001: tired/stressed study case. Morning next day should rank high.
        ["U003", "DEMO001", "C1", "study", "flexible", 60, 1, 48, 0, 22, "Wed", 0, 0, 90, 30, 20, 30, 20, 0, 5, 0.72, 1, 1, 0, 0, 0, 1, 1, "morning", "night", 0, 0, 0, 0, 1],
        ["U003", "DEMO001", "C2", "study", "flexible", 60, 1, 48, 0, 10, "Thu", 0, 1, 120, 60, 120, 110, 110, 0, 2, 0.28, 1, 1, 0, 0, 0, 1, 1, "morning", "morning", 1, 0, 0, 0, 1],
        ["U003", "DEMO001", "C3", "study", "flexible", 60, 1, 48, 0, 15, "Wed", 0, 0, 90, 30, 55, 70, 55, 0, 4, 0.52, 1, 1, 0, 0, 0, 1, 1, "morning", "afternoon", 0, 0, 0, 0, 1],
        ["U003", "DEMO001", "C4", "study", "flexible", 60, 1, 48, 0, 18, "Thu", 0, 1, 75, 15, 40, 35, 35, 0, 5, 0.67, 1, 1, 0, 0, 0, 1, 1, "morning", "evening", 0, 0, 0, 0, 1],
        # DEMO002: overwhelmed personal task. Large gaps and low load should rank high.
        ["U017", "DEMO002", "C1", "personal_task", "flexible", 45, 0, -1, 0, 14, "Mon", 0, 1, 120, 75, 150, 160, 150, 0, 1, 0.16, 0, 0, 1, 0, 0, 1, 1, "afternoon", "afternoon", 1, 1, 15, 20, 1],
        ["U017", "DEMO002", "C2", "personal_task", "flexible", 45, 0, -1, 0, 10, "Tue", 0, 2, 75, 30, 45, 40, 40, 0, 4, 0.58, 0, 0, 1, 0, 0, 1, 1, "afternoon", "morning", 0, 1, 35, 25, 1],
        ["U017", "DEMO002", "C3", "personal_task", "flexible", 45, 0, -1, 0, 17, "Wed", 0, 3, 60, 15, 15, 25, 15, 1, 6, 0.86, 0, 0, 1, 0, 0, 1, 1, "afternoon", "evening", 0, 1, 20, 30, 0],
        ["U017", "DEMO002", "C4", "personal_task", "flexible", 45, 0, -1, 0, 16, "Mon", 0, 1, 90, 45, 95, 100, 95, 0, 2, 0.30, 0, 0, 1, 0, 0, 1, 1, "afternoon", "afternoon", 1, 1, 25, 20, 1],
        # DEMO003: night preference exists, but sad/anxious/deadline patterns still matter.
        ["U030", "DEMO003", "C1", "meeting", "semi_flexible", 90, 1, 36, 0, 21, "Fri", 0, 1, 120, 30, 35, 30, 30, 0, 5, 0.66, 0, 0, 0, 1, 1, 0, 1, "night", "night", 1, 1, 25, 35, 0],
        ["U030", "DEMO003", "C2", "meeting", "semi_flexible", 90, 1, 36, 0, 18, "Thu", 0, 0, 150, 60, 120, 130, 120, 0, 2, 0.26, 0, 0, 0, 1, 1, 0, 1, "night", "evening", 0, 1, 20, 20, 1],
        ["U030", "DEMO003", "C3", "meeting", "semi_flexible", 90, 1, 36, 0, 11, "Fri", 0, 1, 120, 30, 70, 60, 60, 0, 3, 0.43, 0, 0, 0, 1, 1, 0, 1, "night", "morning", 0, 1, 25, 20, 1],
        ["U030", "DEMO003", "C4", "meeting", "semi_flexible", 90, 1, 36, 1, 23, "Sat", 1, 2, 120, 30, 100, 90, 90, 0, 2, 0.34, 0, 0, 0, 1, 1, 0, 1, "night", "night", 1, 1, 15, 20, 1],
    ]
    columns = [
        "user_id", "request_id", "candidate_id", "event_category", "event_flexibility_type",
        "event_duration_min", "has_deadline", "hours_until_deadline", "is_after_deadline",
        "candidate_hour", "candidate_dayofweek", "is_weekend", "days_delayed",
        "candidate_slot_length_min", "extra_time_margin_min", "gap_before_min", "gap_after_min",
        "min_adjacent_gap_min", "is_back_to_back", "num_events_same_day", "schedule_load_score",
        "tired", "stressed", "overwhelmed", "anxious", "sad", "intensity_word", "wants_reschedule",
        "preferred_time_block", "candidate_time_block", "preferred_hour_match", "has_location",
        "travel_time_from_prev_min", "travel_time_to_next_min", "has_travel_buffer",
    ]
    demo_df = pd.DataFrame(demo_rows, columns=columns)
    return demo_df


def score_demo_candidates(model: Pipeline, feature_cols: List[str], demo_df: pd.DataFrame) -> pd.DataFrame:
    pred_proba = model.predict_proba(demo_df[feature_cols])[:, 1]
    scored_demo = demo_df.copy()
    scored_demo["score"] = (pred_proba * 100).round(2)
    scored_demo["rank"] = scored_demo.groupby("request_id")["score"].rank(method="first", ascending=False).astype(int)
    scored_demo = scored_demo.sort_values(["request_id", "rank"])
    return scored_demo


def main() -> None:
    df = generate_dataset()
    validate_dataset(df, has_selected=True)
    data_dictionary = build_data_dictionary()

    df.to_csv(DATASET_PATH, index=False, encoding="utf-8-sig")
    data_dictionary.to_csv(DICTIONARY_PATH, index=False, encoding="utf-8-sig")

    model, feature_cols, metrics = train_evaluate_and_save(df)

    demo_df = make_demo_candidate_input()
    assert "selected" not in demo_df.columns, "Demo input must not include selected."
    demo_df.to_csv(DEMO_INPUT_PATH, index=False, encoding="utf-8-sig")

    scored_demo = score_demo_candidates(model, feature_cols, demo_df)
    scored_demo.to_csv(DEMO_SCORED_PATH, index=False, encoding="utf-8-sig")

    print("\nSynthetic/mock selection log dataset saved:", DATASET_PATH)
    print("Data dictionary saved:", DICTIONARY_PATH)
    print("Scored test predictions saved:", SCORED_TEST_PATH)
    print("Demo candidate input saved:", DEMO_INPUT_PATH)
    print("Demo scored predictions saved:", DEMO_SCORED_PATH)
    print("Logistic Regression model saved:", MODEL_PATH)
    print("Model metrics saved:", METRICS_PATH)

    print("\nValidation summary")
    print("rows:", len(df))
    print("requests:", df["request_id"].nunique())
    print("users:", df["user_id"].nunique())
    print("candidate rows per request:", df.groupby("request_id").size().unique().tolist())
    print("selected sum per request:", df.groupby("request_id")["selected"].sum().unique().tolist())

    print("\nModel metrics")
    for key, value in metrics.items():
        print(f"{key}: {value}")

    print("\nDemo output preview")
    preview_cols = ["request_id", "candidate_id", "candidate_hour", "candidate_dayofweek", "score", "rank"]
    print(scored_demo[preview_cols].to_string(index=False))


if __name__ == "__main__":
    main()
