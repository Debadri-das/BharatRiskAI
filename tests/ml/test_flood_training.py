from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from ml.preprocessing.clean import (
    clean_frame,
    HISTORICAL_FLOOD_FEATURES,
    LEGACY_DEMO_FEATURES,
    FEATURE_SOURCES,
    LEAKAGE_PRONE_FEATURES,
)
from ml.training.train import load_training_data, time_split, train

FEATURES = HISTORICAL_FLOOD_FEATURES


def _dataset(rows: int = 12, features: list[str] | None = None) -> pd.DataFrame:
    feats = features or FEATURES
    frame = pd.DataFrame({feature: np.arange(rows, dtype=float) for feature in feats})
    frame["issue_time"] = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
    frame["target"] = [index % 2 for index in range(rows)]
    return frame


def test_clean_frame_does_not_replace_missing_observations():
    frame = _dataset(2)
    frame.loc[0, "elevation"] = np.nan
    cleaned = clean_frame(frame)
    assert pd.isna(cleaned.loc[0, "elevation"])


def test_training_rejects_duplicate_issue_times(tmp_path: Path):
    frame = _dataset()
    frame.loc[1, "issue_time"] = frame.loc[0, "issue_time"]
    path = tmp_path / "training.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="Duplicate issue-time"):
        load_training_data(path, FEATURES)


def test_training_writes_proxy_metadata_and_model(tmp_path: Path):
    path = tmp_path / "training.csv"
    artifact = tmp_path / "model.joblib"
    _dataset().to_csv(path, index=False)

    result = train(path, FEATURES, "classification", artifact)

    assert artifact.exists()
    assert result["train_rows"] == 9
    assert result["test_rows"] == 3

    payload = joblib.load(artifact)
    assert "scientific_disclaimer" in payload
    assert "not a verified flood prediction" in payload["scientific_disclaimer"]
    assert payload["feature_schema"] == "historical-flood-2020-v1"
    assert "rainfall_1h" in payload["feature_sources"]
    assert "rainfall_3h" in payload["feature_sources"]
    assert "elevation" in payload["feature_sources"]


def test_spatial_tabular_training_with_grid_id(tmp_path: Path):
    # 10 timestamps, 3 grid cells per timestamp = 30 rows
    timestamps = pd.date_range("2020-04-01 00:00", periods=10, freq="30min", tz="UTC")
    grid_cells = ["cell_001", "cell_002", "cell_003"]
    rows = []
    for t_idx, ts in enumerate(timestamps):
        for g_idx, cell in enumerate(grid_cells):
            row = {feat: float(t_idx * 10 + g_idx) for feat in FEATURES}
            row["issue_time"] = ts
            row["grid_id"] = cell
            row["target"] = 1 if (t_idx + g_idx) % 2 == 0 else 0
            rows.append(row)
    df = pd.DataFrame(rows)

    path = tmp_path / "spatial_training.csv"
    df.to_csv(path, index=False)

    # 1. Loading with valid composite key succeeds
    loaded = load_training_data(path, FEATURES)
    assert len(loaded) == 30

    # 2. Duplicate (issue_time, grid_id) is rejected
    df_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    dup_path = tmp_path / "dup.csv"
    df_dup.to_csv(dup_path, index=False)
    with pytest.raises(ValueError, match="Duplicate \\(issue_time, grid_id\\)"):
        load_training_data(dup_path, FEATURES)

    # 3. Time split does not split cells belonging to the same timestamp
    train_df, test_df = time_split(loaded, test_fraction=0.2)
    assert train_df["issue_time"].max() < test_df["issue_time"].min()
    # 10 timestamps -> cut at 80% = 8 timestamps for train (24 rows), 2 for test (6 rows)
    assert len(train_df) == 24
    assert len(test_df) == 6

    # 4. End-to-end model training succeeds
    artifact_path = tmp_path / "spatial_model.joblib"
    result = train(path, FEATURES, "classification", artifact_path)
    assert artifact_path.exists()
    assert result["train_rows"] == 24
    assert result["test_rows"] == 6


def test_event_aware_time_split():
    # 3 events across time
    timestamps_ev1 = pd.date_range("2020-04-01", periods=4, freq="1h", tz="UTC")
    timestamps_ev2 = pd.date_range("2020-05-15", periods=4, freq="1h", tz="UTC")
    timestamps_ev3 = pd.date_range("2020-08-01", periods=4, freq="1h", tz="UTC")
    rows = []
    for ts in timestamps_ev1:
        rows.append({"issue_time": ts, "event_id": "event_1", "target": 1})
    for ts in timestamps_ev2:
        rows.append({"issue_time": ts, "event_id": "event_2", "target": 0})
    for ts in timestamps_ev3:
        rows.append({"issue_time": ts, "event_id": "event_3", "target": 1})
    df = pd.DataFrame(rows)

    train_df, test_df = time_split(df, test_fraction=0.33)
    assert set(train_df["event_id"]) == {"event_1", "event_2"}
    assert set(test_df["event_id"]) == {"event_3"}
    assert train_df["issue_time"].max() < test_df["issue_time"].min()


def test_reject_legacy_demo_risk_score_dataset(tmp_path: Path):
    demo_file = Path("ml/datasets/processed/flood_demo_training.csv")
    if demo_file.exists():
        with pytest.raises(ValueError, match="Legacy demo dataset detected"):
            load_training_data(demo_file, LEGACY_DEMO_FEATURES)


def test_leakage_protection_rejects_static_flood_counts(tmp_path: Path):
    timestamps = pd.date_range("2020-04-01", periods=5, freq="1h", tz="UTC")
    grid_cells = ["cell_A", "cell_B"]
    rows = []
    for ts in timestamps:
        for cell in grid_cells:
            row = {feat: 1.0 for feat in LEGACY_DEMO_FEATURES}
            row["issue_time"] = ts
            row["grid_id"] = cell
            row["target"] = 1
            # Constant static count across all timestamps = leakage
            row["historical_flood_count"] = 5
            row["citizen_report_count"] = 3
            rows.append(row)
    df = pd.DataFrame(rows)
    path = tmp_path / "leaky.csv"
    df.to_csv(path, index=False)

    with pytest.raises(ValueError, match="Temporal leakage detected"):
        load_training_data(path, LEGACY_DEMO_FEATURES)
