from __future__ import annotations

import pandas as pd
from ml.preprocessing.clean import FEATURES, HISTORICAL_FLOOD_FEATURES, LEGACY_DEMO_FEATURES


def validate_frame(df):
    missing = [column for column in FEATURES + ["risk_score"] if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")


def validate_proxy_training_frame(df):
    required = {"issue_time", "target"}
    missing = required - set(df.columns)
    if missing:
        if "risk_score" in df.columns:
            raise ValueError(
                "Invalid training dataset: dataset contains 'risk_score' instead of a timestamped 'target'. "
                "Legacy demo files like flood_demo_training.csv are not valid historical training datasets. "
                "The model requires an 'issue_time' column and a verified binary 'target' (or continuous ground-truth)."
            )
        raise ValueError(f"Missing proxy-training columns: {sorted(missing)}")
    if "grid_id" in df.columns:
        if df.duplicated(subset=["issue_time", "grid_id"]).any():
            raise ValueError("Duplicate (issue_time, grid_id) samples are not allowed")
    else:
        if df["issue_time"].duplicated().any():
            raise ValueError("Duplicate issue-time samples are not allowed")
    values = df["target"].dropna()
    if not values.isin([0, 1]).all():
        raise ValueError("Binary proxy target must contain only 0, 1, or missing values")


def validate_leakage_protection(df: pd.DataFrame, feature_columns: list[str]) -> None:
    """Validate that temporal leakage-prone features have explicit pre-issue timestamps and provenance.

    Historical flood counts and citizen reports must not be static counts; they
    must only reflect observations strictly prior to prediction issue_time.
    """
    for feat in ("historical_flood_count", "citizen_report_count"):
        if feat in feature_columns and feat in df.columns:
            if "issue_time" not in df.columns:
                raise ValueError(
                    f"Temporal leakage risk: '{feat}' is present in a dataset without 'issue_time'. "
                    "Pre-issue provenance cannot be established."
                )
            if "grid_id" in df.columns and df["grid_id"].nunique() > 1 and df["issue_time"].nunique() > 1:
                # Group by grid cell to check if values never change across distinct issue times
                stds = df.groupby("grid_id")[feat].std(ddof=0).fillna(0)
                if (stds == 0).all() and (df[feat] > 0).any():
                    raise ValueError(
                        f"Temporal leakage detected: '{feat}' is static across time for all grid cells. "
                        "Static counts contain future observations; counts must strictly only accumulate "
                        "events occurring prior to each sample's issue_time."
                    )
