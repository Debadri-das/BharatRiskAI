"""Evaluate untouched test predictions per hazard and horizon with validation-selected thresholds."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
HORIZONS = ("+2h", "+3h", "+4h", "+5h", "+6h")


def blocked(reason: str, **details) -> NoReturn:
    report = {"status": "blocked", "reason": reason, "generated_at": datetime.now(timezone.utc).isoformat(), **details}
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "test_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (reports / "test_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["status", "reason"])
        writer.writerow(["blocked", reason])
    raise RuntimeError(f"Evaluation blocked: {reason} (see reports/test_metrics.json).")


def load_thresholds() -> dict[str, dict[str, float | None]]:
    """Read config/alerts.yaml; thresholds must have been selected on validation data."""
    text = (ROOT / "config" / "alerts.yaml").read_text(encoding="utf-8")
    thresholds: dict[str, dict[str, float | None]] = {}
    for hazard in HAZARDS:
        match = re.search(rf"{hazard}:\s*\{{([^}}]*)\}}", text)
        if not match:
            thresholds[hazard] = {horizon: None for horizon in HORIZONS}
            continue
        row: dict[str, float | None] = {}
        for key, value in re.findall(r'"(\+\dh)":\s*([0-9.]+|null)', match.group(1)):
            row[key] = None if value == "null" else float(value)
        thresholds[hazard] = row
    return thresholds


def average_precision(probabilities: np.ndarray, observed: np.ndarray) -> float | None:
    order = np.argsort(-probabilities)
    truth = observed[order]
    positives = float(truth.sum())
    if positives == 0:
        return None
    tp = np.cumsum(truth)
    precision = tp / np.arange(1, truth.size + 1)
    return float(np.sum(precision * truth) / positives)


def roc_auc(probabilities: np.ndarray, observed: np.ndarray) -> float | None:
    positives = float(observed.sum())
    negatives = observed.size - positives
    if positives == 0 or negatives == 0:
        return None  # ROC-AUC is not meaningful without both classes.
    order = np.argsort(probabilities)
    ranks = np.empty(order.size, dtype=np.float64)
    ranks[order] = np.arange(1, order.size + 1)
    for value in np.unique(probabilities):  # average ranks for ties
        member = probabilities == value
        ranks[member] = ranks[member].mean()
    rank_sum_positive = ranks[observed.astype(bool)].sum()
    return float((rank_sum_positive - positives * (positives + 1) / 2) / (positives * negatives))


def binary_metrics(probabilities: np.ndarray, targets: np.ndarray, threshold: float) -> dict[str, float | int | None]:
    predicted = probabilities >= threshold
    observed = targets > 0.5
    tp = float(np.logical_and(predicted, observed).sum())
    fp = float(np.logical_and(predicted, ~observed).sum())
    fn = float(np.logical_and(~predicted, observed).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0  # POD
    return {
        "precision": precision,
        "recall": recall,
        "pod": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "pr_auc": average_precision(probabilities, observed),
        "roc_auc": roc_auc(probabilities, observed),
        "csi": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
        "false_alarm_ratio": fp / (tp + fp) if tp + fp else 0.0,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
        "dice": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "brier": float(np.mean((probabilities - targets) ** 2)),
        "threshold": threshold,
        "samples": int(probabilities.size),
        "positives": int(observed.sum()),
    }


def main() -> None:
    path = ROOT / "data" / "datasets" / "final" / "test_predictions.npz"
    if not path.exists():
        blocked("test_predictions.npz is missing: no trained checkpoint, no held-out test split, and no observed test labels exist. Test metrics cannot be fabricated.")
    thresholds = load_thresholds()
    null_thresholds = [f"{hazard}.{horizon}" for horizon in HORIZONS for hazard in HAZARDS if thresholds.get(hazard, {}).get(horizon) is None]
    if null_thresholds:
        blocked("alert thresholds are null (never selected on validation data); defaulting to 0.5 without evidence is forbidden.", null_thresholds=null_thresholds)
    with np.load(path, allow_pickle=False) as data:
        probabilities = np.asarray(data["probabilities"], dtype=np.float64)
        targets = np.asarray(data["targets"], dtype=np.float64)
    if probabilities.shape != targets.shape or probabilities.ndim != 4 or probabilities.shape[2] != len(HAZARDS):
        blocked(f"unexpected test prediction layout {probabilities.shape} / {targets.shape}; expected [samples, horizons, {len(HAZARDS)}, pixels].")
    if probabilities.shape[1] != len(HORIZONS):
        blocked(f"unexpected horizon count {probabilities.shape[1]}; expected {len(HORIZONS)}.")

    metrics: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for hazard_index, hazard in enumerate(HAZARDS):
        metrics[hazard] = {}
        for horizon_index, horizon in enumerate(HORIZONS):
            probs = probabilities[:, horizon_index, hazard_index].ravel()
            truth = targets[:, horizon_index, hazard_index].ravel()
            finite = np.isfinite(truth)
            if not finite.any():
                blocked(f"no finite known test labels for {hazard} at {horizon}.")
            horizon_threshold = thresholds[hazard][horizon]
            if horizon_threshold is None:
                blocked(f"threshold for {hazard} at {horizon} is null.")
            metrics[hazard][horizon] = binary_metrics(probs[finite], truth[finite], horizon_threshold)

    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload = {"status": "completed", "generated_at": datetime.now(timezone.utc).isoformat(), "evaluated_split": "test", "threshold_fit_split": "validation", "calibration_fit_split": "validation", "metrics": metrics}
    (reports / "test_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (reports / "test_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hazard", "horizon", *next(iter(next(iter(metrics.values())).values())).keys()])
        writer.writeheader()
        for hazard in HAZARDS:
            for horizon in HORIZONS:
                writer.writerow({"hazard": hazard, "horizon": horizon, **metrics[hazard][horizon]})
    print(json.dumps({"status": "completed", "hazards": list(HAZARDS), "horizons": list(HORIZONS)}, indent=2))


if __name__ == "__main__":
    main()