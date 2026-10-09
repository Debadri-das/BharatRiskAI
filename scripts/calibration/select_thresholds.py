"""Select per-hazard and per-horizon operational alert thresholds on validation data only."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
HORIZONS = ("+2h", "+3h", "+4h", "+5h", "+6h")


def calculate_metrics(probabilities: np.ndarray, targets: np.ndarray, threshold: float) -> dict[str, float]:
    """Calculate operational contingency metrics for a decision threshold."""
    predicted = probabilities >= threshold
    observed = targets > 0.5

    tp = float(np.sum(predicted & observed))
    fp = float(np.sum(predicted & ~observed))
    fn = float(np.sum(~predicted & observed))
    tn = float(np.sum(~predicted & ~observed))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0  # POD
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    csi = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    far = fp / (tp + fp) if (tp + fp) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "csi": float(csi),
        "f1": float(f1),
        "pod": float(recall),
        "far": float(far),
        "precision": float(precision),
        "recall": float(recall),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
    }


def select_optimal_threshold(
    probabilities: np.ndarray,
    targets: np.ndarray,
    candidate_thresholds: np.ndarray,
) -> tuple[float, dict[str, float]]:
    """Select the threshold that maximizes CSI (Threat Score) with balanced F1/FAR tie-breaking."""
    best_thresh = None
    best_csi = -1.0
    best_metrics = None

    for thresh in candidate_thresholds:
        metrics = calculate_metrics(probabilities, targets, float(thresh))
        csi = metrics["csi"]
        f1 = metrics["f1"]

        # Objective: Maximize Critical Success Index (CSI / Threat Score)
        if csi > best_csi:
            best_csi = csi
            best_thresh = float(thresh)
            best_metrics = metrics
        elif abs(csi - best_csi) < 1e-7 and best_thresh is not None:
            # Tie-breaking logic: maximize F1, minimize FAR, prefer operational cutoff closest to 0.50
            if f1 > best_metrics["f1"]:
                best_csi = csi
                best_thresh = float(thresh)
                best_metrics = metrics
            elif abs(f1 - best_metrics["f1"]) < 1e-7 and metrics["far"] < best_metrics["far"]:
                best_csi = csi
                best_thresh = float(thresh)
                best_metrics = metrics
            elif abs(f1 - best_metrics["f1"]) < 1e-7 and abs(metrics["far"] - best_metrics["far"]) < 1e-7:
                if abs(thresh - 0.50) < abs(best_thresh - 0.50):
                    best_csi = csi
                    best_thresh = float(thresh)
                    best_metrics = metrics
                elif abs(abs(thresh - 0.50) - abs(best_thresh - 0.50)) < 1e-7 and thresh > best_thresh:
                    best_csi = csi
                    best_thresh = float(thresh)
                    best_metrics = metrics

    return float(best_thresh if best_thresh is not None else 0.5), (best_metrics or calculate_metrics(probabilities, targets, 0.5))


def select_thresholds() -> dict:
    index_path = ROOT / "data" / "datasets" / "final" / "index.csv"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing dataset index at {index_path}.")

    df = pd.read_csv(index_path)

    # 1. Zero Data Leakage Verification (Validation Split Only)
    val_df = df[df["split"].isin(["val", "validation"])].copy()
    val_df["split"] = "val"

    assert set(val_df["split"].unique()) == {"val"}, "Zero Data Leakage violation: split must be exclusively 'val'"
    assert len(val_df) == 7, f"Expected exactly 7 validation samples (Cyclone Yaas), got {len(val_df)}"
    assert set(val_df["event_id"].unique()) == {"2021-05-26"}, f"Validation split must only contain Cyclone Yaas (2021-05-26), got {val_df['event_id'].unique()}"

    validation_pred_path = ROOT / "data" / "datasets" / "final" / "validation_predictions.npz"
    if not validation_pred_path.exists():
        raise FileNotFoundError(f"Validation predictions not found at {validation_pred_path}. Run calibrate stage first.")

    with np.load(validation_pred_path, allow_pickle=False) as data:
        probabilities = np.asarray(data["probabilities"], dtype=np.float64)  # [7, 5, 3, 114, 84]
        targets = np.asarray(data["targets"], dtype=np.float64)              # [7, 5, 3, 114, 84]

    if probabilities.shape != targets.shape:
        raise ValueError(f"Shape mismatch: probabilities {probabilities.shape} != targets {targets.shape}")

    print("=" * 80)
    print("STAGE: ALERT THRESHOLD SELECTION (ZERO DATA LEAKAGE: VALIDATION SPLIT ONLY)")
    print("=" * 80)
    print(f"Validation sequences:   {len(val_df)} (Cyclone Yaas, 2021-05-26)")
    print(f"Optimization Metric:    Critical Success Index (CSI / Threat Score)")
    print(f"Candidate Grid:         0.01 to 0.99 (99 steps)")
    print("-" * 80)

    candidate_thresholds = np.linspace(0.01, 0.99, 99)

    overall_results: dict[str, dict] = {}
    per_horizon_results: dict[str, dict[str, dict]] = {h: {} for h in HAZARDS}

    for h_idx, h_name in enumerate(HAZARDS):
        # Overall optimization across all horizons and samples
        h_prob = probabilities[:, :, h_idx, :, :]
        h_tgt = targets[:, :, h_idx, :, :]
        valid_mask = np.isfinite(h_prob) & np.isfinite(h_tgt) & np.isin(h_tgt, (0, 1))

        best_t, best_m = select_optimal_threshold(h_prob[valid_mask].ravel(), h_tgt[valid_mask].ravel(), candidate_thresholds)
        overall_results[h_name] = {"threshold": best_t, "metrics": best_m}

        # Per-horizon optimization (+2h to +6h)
        for horiz_idx, horiz_name in enumerate(HORIZONS):
            hz_prob = probabilities[:, horiz_idx, h_idx, :, :]
            hz_tgt = targets[:, horiz_idx, h_idx, :, :]
            hz_mask = np.isfinite(hz_prob) & np.isfinite(hz_tgt) & np.isin(hz_tgt, (0, 1))

            hz_best_t, hz_best_m = select_optimal_threshold(hz_prob[hz_mask].ravel(), hz_tgt[hz_mask].ravel(), candidate_thresholds)
            per_horizon_results[h_name][horiz_name] = {"threshold": hz_best_t, "metrics": hz_best_m}

    # Load calibration parameters if present
    cal_params_path = ROOT / "models" / "calibration" / "calibration_params.json"
    cal_info = {}
    if cal_params_path.exists():
        cal_info = json.loads(cal_params_path.read_text(encoding="utf-8"))

    # Persist finalized thresholds to models/checkpoints/thresholds.json
    checkpoint_dir = ROOT / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    thresholds_json_path = checkpoint_dir / "thresholds.json"

    thresholds_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fitted_on": "validation",
        "validation_samples": len(val_df),
        "validation_event_id": "2021-05-26",
        "optimization_metric": "csi",
        "hazard_channels": list(HAZARDS),
        "lead_time_horizons": list(HORIZONS),
        "thresholds": {h: overall_results[h]["threshold"] for h in HAZARDS},
        "per_horizon_thresholds": {
            h: {hz: per_horizon_results[h][hz]["threshold"] for hz in HORIZONS}
            for h in HAZARDS
        },
        "metrics": {
            h: {
                "overall": overall_results[h]["metrics"],
                "per_horizon": {hz: per_horizon_results[h][hz]["metrics"] for hz in HORIZONS},
            }
            for h in HAZARDS
        },
        "calibration_parameters": cal_info.get("models", {}),
    }

    thresholds_json_path.write_text(json.dumps(thresholds_payload, indent=2), encoding="utf-8")

    # Also update config/alerts.yaml for downstream evaluation compatibility
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    alerts_yaml_path = config_dir / "alerts.yaml"

    yaml_lines = ["selection_metric: csi", "fit_split: validation"]
    for h in HAZARDS:
        row = ", ".join(f"\"{hz}\": {per_horizon_results[h][hz]['threshold']}" for hz in HORIZONS)
        yaml_lines.append(f"{h}: {{{row}}}")
    alerts_yaml_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")

    # Reports threshold selection summary
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "threshold_selection.json"
    report_path.write_text(json.dumps({
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fit_split": "validation",
        "test_split_used": False,
        "selection_metric": "csi",
        "candidate_grid": {"start": 0.01, "stop": 0.99, "steps": 99},
        "selected": per_horizon_results,
        "overall_selected": overall_results,
    }, indent=2), encoding="utf-8")

    # Output formatted terminal summary
    print(f"{'Hazard Channel':<18} {'Optimal Cutoff':<16} {'CSI (Threat)':<14} {'POD (Recall)':<14} {'FAR (False Alarm)':<18} {'F1-Score':<10}")
    print("-" * 90)
    for h in HAZARDS:
        m = overall_results[h]["metrics"]
        print(f"{h:<18} {overall_results[h]['threshold']:<16.2f} {m['csi']:<14.4f} {m['pod']:<14.4f} {m['far']:<18.4f} {m['f1']:<10.4f}")
    print("=" * 90)
    print("Lead-Time Horizon Cutoffs (+2h to +6h):")
    for h in HAZARDS:
        hz_strs = [f"{hz}: {per_horizon_results[h][hz]['threshold']:.2f}" for hz in HORIZONS]
        print(f"  {h:<16} -> " + ", ".join(hz_strs))
    print("-" * 90)
    print(f"Serialized JSON artifact:  {thresholds_json_path.relative_to(ROOT)}")
    print(f"Operational config:        {alerts_yaml_path.relative_to(ROOT)}")
    print("THRESHOLD SELECTION COMPLETED SUCCESSFULLY.")
    print("=" * 90)

    return thresholds_payload


def main() -> None:
    select_thresholds()


if __name__ == "__main__":
    main()
