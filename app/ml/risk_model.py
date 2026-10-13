from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERICAL_FEATURES_RISK = [
    "customer_total_jobs",
    "customer_no_show_history_count",
    "scheduled_hour_of_day",
    "scheduled_day_of_week",
    "travel_distance_km",
    "technician_experience_years",
    "lead_time_hours",
]

CATEGORICAL_FEATURES_RISK = [
    "category",
    "urgency",
]

NUMERICAL_INDICES_RISK = list(range(len(NUMERICAL_FEATURES_RISK)))
CATEGORICAL_INDICES_RISK = list(
    range(
        len(NUMERICAL_FEATURES_RISK), len(NUMERICAL_FEATURES_RISK) + len(CATEGORICAL_FEATURES_RISK)
    )
)
ALL_FEATURES_RISK = NUMERICAL_FEATURES_RISK + CATEGORICAL_FEATURES_RISK


class PriorFrequencyRiskBaseline:
    """
    Baseline classifier predicting the marginal positive probability observed on training data.
    """

    def __init__(self) -> None:
        self.prior_probability: float = 0.12

    def fit(
        self, records: list[dict[str, Any]], target_key: str = "is_missed_or_late"
    ) -> "PriorFrequencyRiskBaseline":
        y_vals = [int(r[target_key]) for r in records if target_key in r]
        self.prior_probability = float(np.mean(y_vals)) if y_vals else 0.12
        return self

    def predict_proba(self, records: list[dict[str, Any]]) -> np.ndarray:
        p = self.prior_probability
        probs = np.array([[1.0 - p, p] for _ in records], dtype=float)
        return probs

    def predict(self, records: list[dict[str, Any]], threshold: float = 0.50) -> np.ndarray:
        return np.array([int(self.prior_probability >= threshold) for _ in records], dtype=int)


def build_risk_pipeline(random_state: int = 42) -> Pipeline:
    """
    Constructs a scikit-learn Pipeline with HistGradientBoostingClassifier
    calibrated for imbalanced risk modeling.
    """
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERICAL_INDICES_RISK),
            ("cat", categorical_transformer, CATEGORICAL_INDICES_RISK),
        ]
    )

    classifier = HistGradientBoostingClassifier(
        max_iter=120,
        max_depth=5,
        learning_rate=0.06,
        class_weight="balanced",
        random_state=random_state,
        min_samples_leaf=15,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def extract_risk_matrix(records: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """
    Converts list of record dictionaries into a 2D numpy object matrix and binary target array.
    """
    rows: list[list[Any]] = []
    y: list[int] = []

    for r in records:
        row = [
            r.get("customer_total_jobs", 1),
            r.get("customer_no_show_history_count", 0),
            r.get("scheduled_hour_of_day", 10),
            r.get("scheduled_day_of_week", 1),
            r.get("travel_distance_km") or r.get("distance_km", 10.0),
            r.get("technician_experience_years", 4.0),
            r.get("lead_time_hours", 24.0),
            str(r.get("category", "HVAC")),
            str(r.get("urgency", "MEDIUM")),
        ]
        rows.append(row)
        if "is_missed_or_late" in r:
            y.append(int(r["is_missed_or_late"]))

    X = np.array(rows, dtype=object)
    y_arr = np.array(y, dtype=int) if y else np.empty(0, dtype=int)
    return X, y_arr


def evaluate_classification_metrics(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.50
) -> dict[str, float]:
    """
    Calculates precision, recall, F1, PR-AUC, ROC-AUC, and Brier score (calibration).
    """
    if y_prob.ndim == 2:
        y_prob = y_prob[:, 1]

    y_pred = (y_prob >= threshold).astype(int)

    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    try:
        pr_auc = float(average_precision_score(y_true, y_prob))
    except Exception:
        pr_auc = 0.0

    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        roc_auc = 0.5

    brier = float(brier_score_loss(y_true, y_prob))

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "pr_auc": round(pr_auc, 3),
        "roc_auc": round(roc_auc, 3),
        "brier_score": round(brier, 4),
    }
