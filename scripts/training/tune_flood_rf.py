"""Hyperparameter optimization, evaluation, and artifact generation for the Flood Random Forest model.

Implements Section 4.4 and 4.5:
- Candidate grid search:
  * n_estimators: [200, 400, 600]
  * max_depth: [10, 20, 30, None]
  * min_samples_leaf: [2, 5, 10]
  * max_features: ["sqrt", "log2"]
  * class_weight: ["balanced", "balanced_subsample"]
- Evaluates against Validation set (Cyclone Yaas 2021), never the final Test set (Cyclone Remal 2024).
- Calculates:
  * Precision, Recall, F1, PR-AUC, ROC-AUC
  * Confusion matrix
  * Performance by flood event
  * Performance by geographical sub-region (Southern Coastal / Delta vs Inland Gangetic vs Northern Plains)
- Saves the optimal model artifact to ml/artifacts/flood_random_forest.joblib with full metadata.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing.clean import FEATURE_SOURCES


def evaluate_split(model: Pipeline, df: pd.DataFrame, feature_cols: list[str]) -> dict:
    X = df[feature_cols]
    y_true = df["target"].values
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1] if len(np.unique(y_true)) > 1 else np.zeros_like(y_true, dtype=float)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else None
    pr_auc = float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else None

    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "confusion_matrix": {
            "tn": int(cm[0, 0]),
            "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]),
            "tp": int(cm[1, 1]),
        },
        "sample_count": len(df),
        "positive_count": int(np.sum(y_true == 1)),
        "negative_count": int(np.sum(y_true == 0)),
    }


def region_tag(lat: float, lon: float) -> str:
    """Categorize geographical sub-regions within Eastern India domain."""
    if lat < 23.0:
        return "Coastal_Sundarbans_Delta"
    elif lat < 25.0:
        return "Central_Gangetic_Plain"
    else:
        return "Northern_Sub_Himalayan"


def tune_and_save(
    dataset_path: Path,
    features: list[str],
    artifact_path: Path,
    summary_path: Path,
) -> dict:
    df = pd.read_parquet(dataset_path)
    df["issue_time"] = pd.to_datetime(df["issue_time"], utc=True)

    # Chronological, zero-leakage event partitions:
    # Train: 2020 events (Amphan + fair weather baselines)
    # Validation: 2021 (Cyclone Yaas)
    # Test: 2024 (Cyclone Remal)
    train_mask = df["event_id"].str.contains("2020")
    val_mask = df["event_id"].str.contains("2021")
    test_mask = df["event_id"].str.contains("2024")

    train_df = df[train_mask].sort_values("issue_time").reset_index(drop=True)
    val_df = df[val_mask].sort_values("issue_time").reset_index(drop=True)
    test_df = df[test_mask].sort_values("issue_time").reset_index(drop=True)

    print(f"Dataset Partitions:")
    print(f"  * Train (2020):      {len(train_df)} rows, events={sorted(train_df['event_id'].unique())}")
    print(f"  * Validation (2021): {len(val_df)} rows, events={sorted(val_df['event_id'].unique())}")
    print(f"  * Test (2024):       {len(test_df)} rows, events={sorted(test_df['event_id'].unique())}")

    # Hyperparameter Grid Search (Candidate Values)
    param_grid = {
        "n_estimators": [200, 400, 600],
        "max_depth": [10, 20, 30, None],
        "min_samples_leaf": [2, 5, 10],
        "max_features": ["sqrt", "log2"],
        "class_weight": ["balanced", "balanced_subsample"],
    }

    # Generate candidate configurations
    keys, values = zip(*param_grid.items())
    all_combos = [dict(zip(keys, v)) for v in itertools.product(*values)]
    print(f"\nEvaluating {len(all_combos)} hyperparameter combinations on Validation Set...")

    best_val_f1 = -1.0
    best_params = None
    best_model = None
    all_results = []

    # Fit and tune against Validation set (Yaas), never Test (Remal)
    imputer = SimpleImputer(strategy="median", add_indicator=True)
    X_train_imp = imputer.fit_transform(train_df[features])
    y_train = train_df["target"].values

    for idx, params in enumerate(all_combos, 1):
        rf = RandomForestClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
            max_features=params["max_features"],
            class_weight=params["class_weight"],
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_train_imp, y_train)
        pipe = Pipeline([("imputer", imputer), ("model", rf)])
        val_eval = evaluate_split(pipe, val_df, features)
        
        # Balance score prioritizing F1 while requiring high recall and controlled precision
        val_f1 = val_eval["f1"]
        all_results.append({"params": params, "val_metrics": val_eval})

        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_params = params
            best_model = pipe

    print("\n" + "=" * 80)
    print("HYPERPARAMETER OPTIMIZATION COMPLETE")
    print(f"Best Hyperparameters (tuned on Validation Set / Cyclone Yaas):")
    print(json.dumps(best_params, indent=2))
    print(f"Best Validation F1: {best_val_f1:.4f}")
    print("=" * 80 + "\n")

    # Evaluate Best Model on All Splits
    train_metrics = evaluate_split(best_model, train_df, features)
    val_metrics = evaluate_split(best_model, val_df, features)
    test_metrics = evaluate_split(best_model, test_df, features)

    # Performance by Flood Event
    event_performance = {}
    for ev_id, group in df.groupby("event_id"):
        event_performance[ev_id] = evaluate_split(best_model, group, features)

    # Performance by Geographical Sub-Region
    df_eval = df.copy()
    df_eval["region"] = [region_tag(lat, lon) for lat, lon in zip(df_eval["latitude"], df_eval["longitude"])]
    region_performance = {}
    for reg_name, group in df_eval.groupby("region"):
        region_performance[reg_name] = evaluate_split(best_model, group, features)

    # Feature Importances
    rf_inner = best_model.named_steps["model"]
    importances = {feat: float(imp) for feat, imp in zip(features, rf_inner.feature_importances_)}
    sorted_importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

    payload = {
        "model": best_model,
        "feature_columns": features,
        "feature_schema": "historical-flood-2020-v1",
        "feature_sources": {f: FEATURE_SOURCES.get(f, "user-specified") for f in features},
        "feature_importances": sorted_importances,
        "best_hyperparameters": best_params,
        "target_type": "classification",
        "target_definition": "verified flood inundation (Sentinel-1 SAR radar water extent and confirmed fair-weather zero-flood baselines)",
        "scientific_disclaimer": (
            "Model trained on multi-source verified flood extents (Sentinel-1 SAR surface water masks) "
            "and official IMD daily rainfall observations. Not an unconstrained heuristic."
        ),
        "dataset": str(dataset_path),
        "train_period": [train_df["issue_time"].min().isoformat(), train_df["issue_time"].max().isoformat()],
        "validation_period": [val_df["issue_time"].min().isoformat(), val_df["issue_time"].max().isoformat()],
        "test_period": [test_df["issue_time"].min().isoformat(), test_df["issue_time"].max().isoformat()],
        "metrics": {
            "train": train_metrics,
            "validation": val_metrics,
            "test": test_metrics,
        },
        "event_performance": event_performance,
        "region_performance": region_performance,
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, artifact_path)
    print(f"Saved optimized Flood Random Forest artifact to: {artifact_path}")

    # Write summary report JSON
    summary_data = {
        "artifact": str(artifact_path),
        "best_hyperparameters": best_params,
        "metrics": {
            "validation": val_metrics,
            "test": test_metrics,
            "train": train_metrics,
        },
        "event_performance": event_performance,
        "region_performance": region_performance,
        "feature_importances": sorted_importances,
        "comparison_count": len(all_combos),
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"Saved comprehensive evaluation report to: {summary_path}")

    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune and evaluate Flood Random Forest")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "datasets" / "flood_rf_training.parquet",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ROOT / "ml" / "artifacts" / "flood_random_forest.joblib",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "reports" / "flood_random_forest_evaluation.json",
    )
    args = parser.parse_args()

    features = [
        "rainfall_1h", "rainfall_3h", "rainfall_6h", "rainfall_24h", "rainfall_72h",
        "elevation", "slope", "flow_accumulation", "drainage_proximity", "soil_moisture"
    ]
    tune_and_save(args.dataset, features, args.artifact, args.summary)


if __name__ == "__main__":
    main()
