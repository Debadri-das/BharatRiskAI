"""Select per-hazard, per-horizon alert thresholds from validation data only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
HORIZONS = ("+2h", "+3h", "+4h", "+5h", "+6h")


def scores(probabilities: np.ndarray, targets: np.ndarray, threshold: float) -> dict[str, float]:
    predicted = probabilities >= threshold
    positive = targets > 0.5
    tp = float(np.sum(predicted & positive))
    fp = float(np.sum(predicted & ~positive))
    fn = float(np.sum(~predicted & positive))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    csi = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "csi": csi, "far": fp / (tp + fp) if tp + fp else 0.0}


def main() -> None:
    validation = ROOT / "data" / "datasets" / "final" / "validation_predictions.npz"
    report_path = ROOT / "reports" / "threshold_selection.json"
    if not validation.exists():
        report = {"status": "blocked", "generated_at": datetime.now(timezone.utc).isoformat(), "reason": "No validation predictions exist (no trained model, no validation split). Thresholds must never default to 0.5 without evidence; config/alerts.yaml thresholds remain null.", "fit_split": "validation", "test_split_used": False}
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("Threshold selection blocked: validation predictions missing (see reports/threshold_selection.json).")
    with np.load(validation, allow_pickle=False) as data:
        probabilities = np.asarray(data["probabilities"], dtype=np.float64)
        targets = np.asarray(data["targets"], dtype=np.float64)
    if probabilities.shape != targets.shape or probabilities.ndim != 4:
        raise RuntimeError(f"Threshold selection blocked: expected [samples, horizon, hazards, pixels], got {probabilities.shape} / {targets.shape}.")
    finite = np.isfinite(targets)
    candidates = np.linspace(0.01, 0.99, 99)
    selected: dict[str, dict[str, dict]] = {hazard: {} for hazard in HAZARDS}
    for horizon_index, horizon in enumerate(HORIZONS):
        for hazard_index, hazard in enumerate(HAZARDS):
            mask = finite[:, horizon_index, hazard_index]
            probs = probabilities[mask, horizon_index, hazard_index].ravel()
            truth = targets[mask, horizon_index, hazard_index].ravel()
            best_threshold, best_csi, best_metrics = None, -1.0, None
            for threshold in candidates:
                metrics = scores(probs, truth, float(threshold))
                if metrics["csi"] > best_csi:
                    best_threshold, best_csi, best_metrics = float(threshold), metrics["csi"], metrics
            selected[hazard][horizon] = {"threshold": best_threshold, "validation_metrics": best_metrics}
    lines = ["selection_metric: csi", "fit_split: validation"]
    for hazard in HAZARDS:
        row = ", ".join(f"\"{horizon}\": {selected[hazard][horizon]['threshold']}" for horizon in HORIZONS)
        lines.append(f"{hazard}: {{{row}}}")
    (ROOT / "config" / "alerts.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {"status": "completed", "generated_at": datetime.now(timezone.utc).isoformat(), "fit_split": "validation", "test_split_used": False, "selection_metric": "csi", "candidate_grid": {"start": 0.01, "stop": 0.99, "steps": 99}, "selected": selected}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()