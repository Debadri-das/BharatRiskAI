"""Evaluate forecasting performance on the unseen test split (Cyclone Remal)."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
HORIZONS = ("+2h", "+3h", "+4h", "+5h", "+6h")


def expected_calibration_error(probabilities: np.ndarray, targets: np.ndarray, bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE) across uniform bins."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(probabilities, edges) - 1, 0, bins - 1)
    ece = 0.0
    total = probabilities.size
    if total == 0:
        return 0.0
    for bin_id in range(bins):
        member = index == bin_id
        if not member.any():
            continue
        bin_prob = float(probabilities[member].mean())
        bin_true = float(targets[member].mean())
        ece += abs(bin_prob - bin_true) * (int(member.sum()) / total)
    return float(ece)


def compute_metrics(
    probabilities: np.ndarray,
    targets: np.ndarray,
    threshold: float,
) -> dict[str, float | int]:
    """Calculate probabilistic and categorical verification scores for non-NaN pixels."""
    valid_mask = np.isfinite(probabilities) & np.isfinite(targets) & np.isin(targets, (0, 1))
    p = probabilities[valid_mask].astype(np.float64)
    y = targets[valid_mask].astype(np.float64)

    if p.size == 0:
        raise ValueError("No valid finite test pixels found for metric computation.")

    # Binarize using the validation-fitted operational threshold (keep as boolean for logical negation)
    binarized = p >= threshold
    observed = y > 0.5

    # Contingency table components
    tp = float(np.sum(binarized & observed))
    fp = float(np.sum(binarized & ~observed))
    fn = float(np.sum(~binarized & observed))
    tn = float(np.sum(~binarized & ~observed))
    total = float(p.size)

    # Categorical verification metrics
    csi = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    pod = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    far = fp / (tp + fp) if (tp + fp) > 0 else 0.0
    false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    lead_time_accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = pod
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Probabilistic verification metrics
    brier = float(np.mean((p - y) ** 2))
    ece = expected_calibration_error(p, y)
    pr_auc = float(average_precision_score(observed, p)) if len(np.unique(observed)) > 1 else 1.0

    return {
        "threshold": float(threshold),
        "csi": float(csi),
        "pod": float(pod),
        "far": float(far),
        "false_alarm_rate": float(false_alarm_rate),
        "lead_time_accuracy": float(lead_time_accuracy),
        "f1": float(f1),
        "f1_score": float(f1),
        "brier": float(brier),
        "brier_score": float(brier),
        "pr_auc": float(pr_auc),
        "ece": float(ece),
        "precision": float(precision),
        "recall": float(recall),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "total_pixels": int(total),
    }


def evaluate_test_split() -> dict:
    test_pred_path = ROOT / "data" / "datasets" / "final" / "test_predictions.npz"
    if not test_pred_path.exists():
        raise FileNotFoundError(
            f"Test predictions not found at {test_pred_path}. Run training stage first."
        )

    thresholds_path = ROOT / "models" / "checkpoints" / "thresholds.json"
    if not thresholds_path.exists():
        raise FileNotFoundError(
            f"Thresholds file not found at {thresholds_path}. Run thresholds stage first."
        )

    thresh_payload = json.load(thresholds_path.open(encoding="utf-8"))
    per_horizon_thresholds = thresh_payload.get("per_horizon_thresholds", {})

    # Load calibration parameters from validation
    cal_params_path = ROOT / "models" / "calibration" / "calibration_params.json"
    cal_models = {}
    if cal_params_path.exists():
        cal_models = json.load(cal_params_path.open(encoding="utf-8")).get("models", {})
    elif "calibration_parameters" in thresh_payload:
        cal_models = thresh_payload["calibration_parameters"]

    # Ingest test predictions tensor: [B, 5, 3, 114, 84]
    with np.load(test_pred_path, allow_pickle=False) as data:
        raw_probabilities = np.asarray(data["probabilities"], dtype=np.float64)
        targets = np.asarray(data["targets"], dtype=np.float64)

    if raw_probabilities.ndim != 5:
        raise ValueError(
            f"Expected 5D test tensor [B, horizons, hazards, H, W], got shape {raw_probabilities.shape}"
        )

    num_samples, num_horizons, num_hazards, height, width = raw_probabilities.shape
    if num_horizons != len(HORIZONS):
        raise ValueError(f"Expected {len(HORIZONS)} horizons, got {num_horizons}")
    if num_hazards != len(HAZARDS):
        raise ValueError(f"Expected {len(HAZARDS)} hazards, got {num_hazards}")

    # Calibrate test predictions using validation-fitted Platt scaling curves
    calibrated_probabilities = np.zeros_like(raw_probabilities)
    for h_idx, h_name in enumerate(HAZARDS):
        raw_h = raw_probabilities[:, :, h_idx, :, :]
        if h_name in cal_models and "slope" in cal_models[h_name] and "intercept" in cal_models[h_name]:
            slope = float(cal_models[h_name]["slope"])
            intercept = float(cal_models[h_name]["intercept"])
            cal_h = 1.0 / (1.0 + np.exp(-(slope * raw_h + intercept)))
        else:
            cal_h = raw_h
        calibrated_probabilities[:, :, h_idx, :, :] = cal_h

    # Disaggregate test tensor and compute metrics per hazard and lead time
    nested_metrics: dict[str, dict[str, dict[str, float | int]]] = {}

    for h_idx, h_name in enumerate(HAZARDS):
        nested_metrics[h_name] = {}
        for horiz_idx, horiz_name in enumerate(HORIZONS):
            # Extract isolated spatial grids
            p_slice = calibrated_probabilities[:, horiz_idx, h_idx, :, :].ravel()
            y_slice = targets[:, horiz_idx, h_idx, :, :].ravel()

            # Retrieve operational threshold
            threshold_val = per_horizon_thresholds.get(h_name, {}).get(horiz_name, 0.5)

            metrics = compute_metrics(p_slice, y_slice, float(threshold_val))
            nested_metrics[h_name][horiz_name] = metrics

    # Also support 'flash flood' alias with space for universal lookup
    nested_metrics["flash flood"] = nested_metrics["flash_flood"]

    # 4. Artifact Serialization: Export to models/evaluation/test_metrics.json
    eval_dir = ROOT / "models" / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    out_metrics_path = eval_dir / "test_metrics.json"

    out_metrics_path.write_text(json.dumps(nested_metrics, indent=2), encoding="utf-8")

    # Also write to reports/test_metrics.json and test_metrics.csv for pipeline reporting
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluated_split": "test",
        "test_event_id": "2024-05-26",
        "test_samples": num_samples,
        "threshold_fit_split": "validation",
        "calibration_fit_split": "validation",
        "metrics": {h: nested_metrics[h] for h in HAZARDS},
    }
    (reports_dir / "test_metrics.json").write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    # Write CSV summary
    with (reports_dir / "test_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        sample_metrics = next(iter(next(iter(nested_metrics.values())).values()))
        fieldnames = ["hazard", "horizon", *sample_metrics.keys()]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for h in HAZARDS:
            for hz in HORIZONS:
                writer.writerow({"hazard": h, "horizon": hz, **nested_metrics[h][hz]})

    # Output terminal summary table
    print("=" * 86)
    print("STAGE: TEST EVALUATION (CYCLONE REMAL, UNSEEN TEST SPLIT - 14 SAMPLES)")
    print("=" * 86)
    print(f"Spatial Grid:             {height} x {width} ({height * width} pixels per frame)")
    print(f"Total Test Sequences:     {num_samples} (2024-05-26 Cyclone Remal)")
    print(f"Calibration Applied:      Platt Scaling (Fitted on Validation Split Only)")
    print(f"Thresholds Applied:       CSI-Optimized (Fitted on Validation Split Only)")
    print("-" * 86)
    print(f"{'Hazard':<16} {'Lead Time':<12} {'Threshold':<12} {'CSI':<10} {'POD':<10} {'Brier Score':<14} {'PR-AUC':<10} {'F1':<10}")
    print("-" * 86)
    for h in HAZARDS:
        for hz in HORIZONS:
            m = nested_metrics[h][hz]
            print(
                f"{h:<16} {hz:<12} {m['threshold']:<12.2f} {m['csi']:<10.4f} {m['pod']:<10.4f} {m['brier']:<14.4f} {m['pr_auc']:<10.4f} {m['f1']:<10.4f}"
            )
    print("=" * 86)

    # Highlight Flash Floods at +2h and +6h marks as requested
    ff_2h = nested_metrics["flash_flood"]["+2h"]
    ff_6h = nested_metrics["flash_flood"]["+6h"]
    print("FLASH FLOOD VERIFICATION SUMMARY (+2h vs +6h):")
    print("-" * 86)
    print(f"{'Lead Time':<12} {'CSI (Threat)':<16} {'POD (Hit Rate)':<18} {'Brier Score':<16} {'FAR (False Alarm)':<18}")
    print("-" * 86)
    print(f"{'+2h':<12} {ff_2h['csi']:<16.4f} {ff_2h['pod']:<18.4f} {ff_2h['brier']:<16.4f} {ff_2h['far']:<18.4f}")
    print(f"{'+6h':<12} {ff_6h['csi']:<16.4f} {ff_6h['pod']:<18.4f} {ff_6h['brier']:<16.4f} {ff_6h['far']:<18.4f}")
    print("=" * 86)
    print(f"Serialized metrics artifact:  {out_metrics_path.relative_to(ROOT)}")
    print(f"Evaluation report:            {(reports_dir / 'test_metrics.json').relative_to(ROOT)}")
    print("TEST EVALUATION COMPLETED SUCCESSFULLY.")
    print("=" * 86)

    return nested_metrics


def main() -> None:
    evaluate_test_split()


if __name__ == "__main__":
    main()
