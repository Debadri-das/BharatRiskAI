"""Fit validation-only temperature scaling for multi-task probabilities."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def fit_temperature(logits: np.ndarray, targets: np.ndarray) -> float:
    candidates = np.exp(np.linspace(-2.0, 2.0, 81))
    scores = []
    for temperature in candidates:
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits / temperature, -30, 30)))
        scores.append(float(np.mean(-(targets * np.log(probabilities + 1e-7) + (1 - targets) * np.log(1 - probabilities + 1e-7)))))
    return float(candidates[int(np.argmin(scores))])


def brier(probabilities: np.ndarray, targets: np.ndarray) -> float:
    return float(np.mean((probabilities - targets) ** 2))


def expected_calibration_error(probabilities: np.ndarray, targets: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(probabilities, edges) - 1, 0, bins - 1)
    ece = 0.0
    for bin_id in range(bins):
        member = index == bin_id
        if not member.any():
            continue
        ece += abs(float(probabilities[member].mean()) - float(targets[member].mean())) * int(member.sum()) / int(probabilities.size)
    return ece


def reliability_bins(probabilities: np.ndarray, targets: np.ndarray, bins: int = 10) -> list[dict]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(probabilities, edges) - 1, 0, bins - 1)
    rows = []
    for bin_id in range(bins):
        member = index == bin_id
        if not member.any():
            continue
        rows.append({"bin": [float(edges[bin_id]), float(edges[bin_id + 1])], "count": int(member.sum()), "mean_predicted": float(probabilities[member].mean()), "observed_fraction": float(targets[member].mean())})
    return rows


def main() -> None:
    validation = ROOT / "data" / "datasets" / "final" / "validation_predictions.npz"
    output = ROOT / "models" / "calibration"
    output.mkdir(parents=True, exist_ok=True)
    if not validation.exists():
        report = {"status": "blocked", "generated_at": datetime.now(timezone.utc).isoformat(), "reason": "validation_predictions.npz is missing; there is no trained model and no validation split. Calibration must use validation data only and must never be fitted on test data."}
        (output / "calibration_blocked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (ROOT / "reports" / "calibration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("Calibration blocked: validation_predictions.npz is missing (see models/calibration/calibration_blocked.json).")
    with np.load(validation, allow_pickle=False) as data:
        logits = np.asarray(data["logits"], dtype=np.float64).ravel()
        targets = np.asarray(data["targets"], dtype=np.float64).ravel()
    finite = np.isfinite(logits) & np.isfinite(targets)
    logits, targets = logits[finite], targets[finite]
    if not targets.size:
        report = {"status": "blocked", "generated_at": datetime.now(timezone.utc).isoformat(), "reason": "validation predictions contain no finite known-label samples."}
        (output / "calibration_blocked.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (ROOT / "reports" / "calibration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("Calibration blocked: no finite known-label validation samples.")

    temperature = fit_temperature(logits, targets)
    raw = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))
    calibrated = 1.0 / (1.0 + np.exp(-np.clip(logits / temperature, -30, 30)))
    report = {
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "temperature_scaling",
        "fit_split": "validation",
        "test_split_used": False,
        "samples": int(targets.size),
        "temperature": temperature,
        "raw_brier_score": brier(raw, targets),
        "calibrated_brier_score": brier(calibrated, targets),
        "ece_raw": expected_calibration_error(raw, targets),
        "ece_calibrated": expected_calibration_error(calibrated, targets),
        "reliability_bins_raw": reliability_bins(raw, targets),
        "reliability_bins_calibrated": reliability_bins(calibrated, targets),
    }
    (output / "temperature.json").write_text(json.dumps({"method": "temperature_scaling", "fit_split": "validation", "temperature": temperature}, indent=2), encoding="utf-8")
    (ROOT / "reports" / "calibration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()