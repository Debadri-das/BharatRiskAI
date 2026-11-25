"""Train the Flood Random Forest from a user-supplied, time-indexed dataset.

No demo file, synthetic observation, or synthetic target is created here.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
    r2_score,
)

from ml.models.random_forest import build_model
from ml.preprocessing.clean import (
    FEATURES,
    HISTORICAL_FLOOD_FEATURES,
    LEGACY_DEMO_FEATURES,
    FEATURE_SOURCES,
    LEAKAGE_PRONE_FEATURES,
)
from ml.preprocessing.validation import (
    validate_proxy_training_frame,
    validate_leakage_protection,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT = ROOT / "ml" / "artifacts" / "flood_random_forest.joblib"


def time_split(frame: pd.DataFrame, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological, event-aware train/test split.
    
    Guarantees no cross-cell or cross-event leakage across the split boundary.
    All spatial cells for a given issue_time or event remain in the same partition.
    """
    if "issue_time" not in frame:
        raise ValueError("Training data must include issue_time for a time-based split")

    # If event_id is present, group chronologically by event
    if "event_id" in frame.columns and frame["event_id"].notna().any():
        event_times = frame.groupby("event_id")["issue_time"].min().sort_values()
        unique_events = event_times.index.tolist()
        if len(unique_events) > 1:
            cut_idx = max(1, int(round(len(unique_events) * (1 - test_fraction))))
            cut_idx = min(cut_idx, len(unique_events) - 1)
            train_events = set(unique_events[:cut_idx])
            test_events = set(unique_events[cut_idx:])
            train = frame[frame["event_id"].isin(train_events)].sort_values("issue_time").reset_index(drop=True)
            test = frame[frame["event_id"].isin(test_events)].sort_values("issue_time").reset_index(drop=True)
            if test.empty or train.empty:
                raise ValueError("Training data does not contain a non-empty temporal test period")
            if train["issue_time"].max() >= test["issue_time"].min():
                raise ValueError("Temporal split overlaps")
            return train, test

    # Otherwise, split by unique timestamps chronologically
    unique_times = frame["issue_time"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(unique_times) < 2:
        raise ValueError("Training data must contain multiple timestamps for a time-based split")

    cut_idx = max(1, int(len(unique_times) * (1 - test_fraction)))
    cut_idx = min(cut_idx, len(unique_times) - 1)
    train_times = set(unique_times.iloc[:cut_idx])
    test_times = set(unique_times.iloc[cut_idx:])

    train = frame[frame["issue_time"].isin(train_times)].sort_values("issue_time").reset_index(drop=True)
    test = frame[frame["issue_time"].isin(test_times)].sort_values("issue_time").reset_index(drop=True)

    if test.empty or train.empty:
        raise ValueError("Training data does not contain a non-empty temporal test period")
    if train["issue_time"].max() >= test["issue_time"].min():
        raise ValueError("Temporal split overlaps")
    return train, test


def load_training_data(
    path: str | Path, feature_columns: list[str], target_column: str = "target"
) -> pd.DataFrame:
    frame = pd.read_parquet(path) if Path(path).suffix.lower() == ".parquet" else pd.read_csv(path)
    
    # Reject legacy demo files containing risk_score without a verified target
    if "risk_score" in frame.columns and target_column not in frame.columns:
        raise ValueError(
            "Legacy demo dataset detected (contains 'risk_score' without 'target'). "
            "Files like flood_demo_training.csv are not valid historical training datasets. "
            "Real models require timestamped observations ('issue_time') and verified targets."
        )

    required = {"issue_time", target_column, *feature_columns}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Training dataset is missing columns: {sorted(missing)}")
    frame["issue_time"] = pd.to_datetime(frame["issue_time"], utc=True, errors="raise")
    if "grid_id" in frame.columns:
        if frame.duplicated(subset=["issue_time", "grid_id"]).any():
            raise ValueError("Duplicate (issue_time, grid_id) samples are not allowed")
    else:
        if frame.duplicated(subset=["issue_time"]).any():
            raise ValueError("Duplicate issue-time samples are not allowed")
    if target_column == "target":
        validate_proxy_training_frame(frame)
    validate_leakage_protection(frame, feature_columns)
    usable = frame[frame[target_column].notna()].copy()
    if usable.empty:
        raise ValueError("No usable target rows remain; missing future observations are not negatives")
    return usable


def train(
    path: str | Path, feature_columns: list[str], target_type: str, artifact: str | Path = DEFAULT_ARTIFACT
) -> dict:
    frame = load_training_data(path, feature_columns)
    if target_type == "classification" and not frame["target"].isin([0, 1]).all():
        raise ValueError("Classification training requires a binary 0/1 proxy target")
    train_frame, test_frame = time_split(frame)
    if target_type == "classification" and train_frame["target"].nunique() < 2:
        raise ValueError("The temporal training period must contain both proxy-target classes")
    model = build_model(target_type)
    model.fit(train_frame[feature_columns], train_frame["target"])
    predictions = model.predict(test_frame[feature_columns])
    if target_type == "classification":
        metrics = {
            "precision": precision_score(test_frame["target"], predictions, zero_division=0),
            "recall": recall_score(test_frame["target"], predictions, zero_division=0),
            "f1": f1_score(test_frame["target"], predictions, zero_division=0),
            "class_balance": test_frame["target"].value_counts(normalize=True).to_dict(),
        }
        if len(set(test_frame["target"])) > 1:
            probabilities = model.predict_proba(test_frame[feature_columns])[:, 1]
            metrics.update(
                {
                    "roc_auc": roc_auc_score(test_frame["target"], probabilities),
                    "pr_auc": average_precision_score(test_frame["target"], probabilities),
                }
            )
    else:
        metrics = {
            "mae": mean_absolute_error(test_frame["target"], predictions),
            "rmse": mean_squared_error(test_frame["target"], predictions) ** 0.5,
            "r2": r2_score(test_frame["target"], predictions),
        }
    payload = {
        "model": model,
        "feature_columns": feature_columns,
        "feature_schema": "historical-flood-2020-v1",
        "feature_sources": {f: FEATURE_SOURCES.get(f, "user-specified") for f in feature_columns},
        "target_type": target_type,
        "target_definition": "future satellite-derived proxy target (extreme rainfall proxy; not verified flood inundation)",
        "scientific_disclaimer": (
            "A model trained to predict future heavy rainfall (QPE proxy) is an extreme rainfall classifier, "
            "not a verified flood prediction or inundation model. Genuine flood modeling requires ground-truth "
            "flood extent, stage gauge measurements, or verified flood damage reports."
        ),
        "dataset": str(path),
        "train_period": [train_frame["issue_time"].min().isoformat(), train_frame["issue_time"].max().isoformat()],
        "test_period": [test_frame["issue_time"].min().isoformat(), test_frame["issue_time"].max().isoformat()],
        "metrics": metrics,
    }
    destination = Path(artifact)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, destination)
    return {
        "artifact": str(destination),
        "metrics": metrics,
        "train_rows": len(train_frame),
        "test_rows": len(test_frame),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--features", nargs="+", default=HISTORICAL_FLOOD_FEATURES)
    parser.add_argument("--target-type", choices=["classification", "regression"], required=True)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    print(json.dumps(train(args.dataset, args.features, args.target_type, args.artifact), indent=2, default=str))


if __name__ == "__main__":
    main()
