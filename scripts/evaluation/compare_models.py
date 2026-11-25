"""Model comparison benchmark: Evaluates multiple classification models on unseen test data.

Compares:
- Random Forest (Baseline)
- LightGBM (Gradient Boosting Framework)
- HistGradientBoosting (Scikit-Learn Gradient Boosting)
- Extra Trees
- Logistic Regression (Linear Baseline)

Evaluates on the held-out test event (Cyclone Remal 2024).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]

FEATURES = [
    "rainfall_1h",
    "rainfall_3h",
    "rainfall_6h",
    "rainfall_24h",
    "rainfall_72h",
    "elevation",
    "slope",
    "flow_accumulation",
    "drainage_proximity",
    "soil_moisture",
]


def load_dataset(parquet_path: Path):
    df = pd.read_parquet(parquet_path)
    train_mask = df["event_id"].isin([
        "fair_weather_2020_04_01",
        "fair_weather_2020_04_06",
        "fair_weather_2020_04_14",
        "cyclone_amphan_2020",
    ])
    val_mask = df["event_id"] == "cyclone_yaas_2021"
    test_mask = df["event_id"] == "cyclone_remal_2024"

    return df[train_mask], df[val_mask], df[test_mask]


def build_pipeline(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", model),
    ])


def evaluate_model(pipeline, X_train, y_train, X_test, y_test):
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    if hasattr(pipeline, "predict_proba"):
        y_prob = pipeline.predict_proba(X_test)[:, 1]
    elif hasattr(pipeline, "decision_function"):
        y_prob = pipeline.decision_function(X_test)
    else:
        y_prob = y_pred

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    try:
        roc = float(roc_auc_score(y_test, y_prob))
    except Exception:
        roc = 0.5

    try:
        pr_auc = float(average_precision_score(y_test, y_prob))
    except Exception:
        pr_auc = 0.0

    return {
        "Accuracy (%)": round(acc * 100, 2),
        "Precision": round(prec, 4),
        "Recall": round(rec, 4),
        "F1-Score": round(f1, 4),
        "ROC-AUC": round(roc, 4),
        "PR-AUC": round(pr_auc, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare ML models on flood hazard dataset")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "datasets" / "flood_rf_training.parquet",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ROOT / "reports" / "model_comparison.csv",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "reports" / "model_comparison.json",
    )
    args = parser.parse_args()

    train_df, val_df, test_df = load_dataset(args.dataset)
    X_train, y_train = train_df[FEATURES], train_df["target"].values
    X_test, y_test = test_df[FEATURES], test_df["target"].values

    models = {
        "Random Forest (Baseline)": RandomForestClassifier(
            n_estimators=200, max_depth=20, min_samples_leaf=2, random_state=42, class_weight="balanced"
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=200, random_state=42, class_weight="balanced"
        ),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=200, max_depth=20, min_samples_leaf=2, random_state=42, class_weight="balanced"
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=1000, random_state=42, class_weight="balanced"
        ),
    }

    try:
        import lightgbm as lgb
        models["LightGBM"] = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.05, num_leaves=31, random_state=42, class_weight="balanced"
        )
    except ImportError:
        print("[INFO] lightgbm not installed. Run 'pip install lightgbm' to include LightGBM in comparison.")

    results = []
    print(f"\nComparing {len(models)} models on Test Set (Cyclone Remal 2024, N={len(test_df)})...")
    print("=" * 80)

    for name, model in models.items():
        print(f"Training & Evaluating: {name} ...", end=" ", flush=True)
        pipe = build_pipeline(model)
        metrics = evaluate_model(pipe, X_train, y_train, X_test, y_test)
        metrics["Model"] = name
        results.append(metrics)
        print("Done.")

    results_df = pd.DataFrame(results)[
        ["Model", "Accuracy (%)", "Precision", "Recall", "F1-Score", "ROC-AUC", "PR-AUC"]
    ].sort_values(by="F1-Score", ascending=False)

    print("\n" + "=" * 80)
    print("MODEL COMPARISON RESULTS (TEST SET: CYCLONE REMAL 2024)")
    print("=" * 80)
    print(results_df.to_string(index=False))
    print("=" * 80)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(args.output_csv, index=False)
    args.output_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[OK] Reports saved to:")
    print(f"  - CSV : {args.output_csv}")
    print(f"  - JSON: {args.output_json}\n")


if __name__ == "__main__":
    main()
