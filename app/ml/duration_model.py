from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERICAL_FEATURES_DURATION = [
    "equipment_age_years",
    "technician_experience_years",
    "technician_active_jobs_count",
    "historical_jobs_completed",
    "distance_km",
    "estimated_duration_minutes",
]

CATEGORICAL_FEATURES_DURATION = [
    "category",
    "equipment_type",
    "urgency",
]

NUMERICAL_INDICES_DURATION = list(range(len(NUMERICAL_FEATURES_DURATION)))
CATEGORICAL_INDICES_DURATION = list(
    range(
        len(NUMERICAL_FEATURES_DURATION),
        len(NUMERICAL_FEATURES_DURATION) + len(CATEGORICAL_FEATURES_DURATION),
    )
)
ALL_FEATURES_DURATION = NUMERICAL_FEATURES_DURATION + CATEGORICAL_FEATURES_DURATION


class HistoricalCategoryAverageBaseline:
    """
    Baseline model that predicts job duration using the historical mean of the issue category.
    Falls back to global training mean for unseen categories.
    """

    def __init__(self) -> None:
        self.category_means: dict[str, float] = {}
        self.global_mean: float = 60.0

    def fit(
        self, records: list[dict[str, Any]], target_key: str = "actual_duration_minutes"
    ) -> "HistoricalCategoryAverageBaseline":
        y_vals = [float(r[target_key]) for r in records if target_key in r]
        self.global_mean = float(np.mean(y_vals)) if y_vals else 60.0

        cat_groups: dict[str, list[float]] = {}
        for r in records:
            cat = str(r.get("category", "UNKNOWN"))
            val = float(r.get(target_key, self.global_mean))
            cat_groups.setdefault(cat, []).append(val)

        self.category_means = {cat: float(np.mean(vals)) for cat, vals in cat_groups.items()}
        return self

    def predict(self, records: list[dict[str, Any]]) -> np.ndarray:
        preds = [self.category_means.get(str(r.get("category")), self.global_mean) for r in records]
        return np.array(preds, dtype=float)


def build_duration_pipeline(random_state: int = 42) -> Pipeline:
    """
    Constructs a scikit-learn Pipeline with clean preprocessing and HistGradientBoostingRegressor.
    Preprocesses numeric and categorical features without data leakage.
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
            ("num", numeric_transformer, NUMERICAL_INDICES_DURATION),
            ("cat", categorical_transformer, CATEGORICAL_INDICES_DURATION),
        ]
    )

    regressor = HistGradientBoostingRegressor(
        max_iter=150,
        max_depth=6,
        learning_rate=0.08,
        random_state=random_state,
        min_samples_leaf=15,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )


def extract_duration_matrix(records: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """
    Converts list of record dictionaries into a 2D numpy object matrix and target array.
    """
    rows: list[list[Any]] = []
    y: list[float] = []

    for r in records:
        row = [
            r.get("equipment_age_years"),
            r.get("technician_experience_years"),
            r.get("technician_active_jobs_count", 0),
            r.get("historical_jobs_completed", 0),
            r.get("distance_km") or r.get("travel_distance_km", 10.0),
            r.get("estimated_duration_minutes", 60.0),
            str(r.get("category", "HVAC")),
            str(r.get("equipment_type") or "missing"),
            str(r.get("urgency", "MEDIUM")),
        ]
        rows.append(row)
        if "actual_duration_minutes" in r:
            y.append(float(r["actual_duration_minutes"]))

    X = np.array(rows, dtype=object)
    y_arr = np.array(y, dtype=float) if y else np.empty(0, dtype=float)
    return X, y_arr


def evaluate_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """
    Calculates standard regression evaluation metrics: MAE, RMSE, and R2.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 3),
    }
