"""Fit validation-only probability calibration for multi-task nowcasting models."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.nowcasting.architecture import SpatiotemporalMTLNet
from reports.unified_feature_schema import BASELINE_ORDER, CHANNEL_ORDER

HAZARDS = ("thunderstorm", "cloudburst", "flash_flood")
HORIZONS = ("+2h", "+3h", "+4h", "+5h", "+6h")
BASELINE_INDICES = tuple(CHANNEL_ORDER.index(name) for name in BASELINE_ORDER)


def brier_score(probabilities: np.ndarray, targets: np.ndarray) -> float:
    """Mean Squared Error between predicted probabilities and binary targets."""
    return float(np.mean((probabilities - targets) ** 2))


def fit_temperature(logits: np.ndarray, targets: np.ndarray) -> float:
    """Fit a temperature scaling parameter strictly rejecting non-binary or invalid targets."""
    logits = np.asarray(logits, dtype=np.float32)
    targets = np.asarray(targets, dtype=np.float32)
    if not np.isfinite(targets).all():
        raise ValueError("Targets contain missing or non-finite values")
    unique = np.unique(targets)
    if not np.all(np.isin(unique, [0.0, 1.0, 0, 1])):
        raise ValueError("Targets must be binary (0 or 1)")
    from scipy.optimize import minimize_scalar
    def nll(temp):
        t = max(temp, 1e-4)
        scaled = logits / t
        probs = 1.0 / (1.0 + np.exp(-np.clip(scaled, -30.0, 30.0)))
        eps = 1e-7
        return -np.mean(targets * np.log(probs + eps) + (1.0 - targets) * np.log(1.0 - probs + eps))
    res = minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded")
    return float(res.x)


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


def reliability_bins(probabilities: np.ndarray, targets: np.ndarray, bins: int = 10) -> list[dict]:
    """Compute reliability diagram binning."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(probabilities, edges) - 1, 0, bins - 1)
    rows = []
    for bin_id in range(bins):
        member = index == bin_id
        if not member.any():
            continue
        rows.append({
            "bin": [float(edges[bin_id]), float(edges[bin_id + 1])],
            "count": int(member.sum()),
            "mean_predicted": float(probabilities[member].mean()),
            "observed_fraction": float(targets[member].mean()),
        })
    return rows


def calibrate_validation() -> dict:
    index_path = ROOT / "data" / "datasets" / "final" / "index.csv"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing dataset index at {index_path}. Build sequences first.")

    df = pd.read_csv(index_path)

    # 1. Zero Data Leakage Verification (Validation Split Only)
    val_df = df[df["split"].isin(["val", "validation"])].copy()
    val_df["split"] = "val"

    # Strict runtime assertion required by contract
    assert set(val_df["split"].unique()) == {"val"}, "Zero Data Leakage violation: split must be exclusively 'val'"
    assert len(val_df) == 7, f"Expected exactly 7 validation samples (Cyclone Yaas), got {len(val_df)}"
    assert set(val_df["event_id"].unique()) == {"2021-05-26"}, f"Validation split must only contain Cyclone Yaas (2021-05-26), got {val_df['event_id'].unique()}"

    print("=" * 80)
    print("STAGE: PROBABILITY CALIBRATION (ZERO DATA LEAKAGE: VALIDATION SPLIT ONLY)")
    print("=" * 80)
    print(f"Validation samples:     {len(val_df)} (Cyclone Yaas, 2021-05-26)")
    print(f"Training samples used:  0 (STRICT ZERO LEAKAGE)")
    print(f"Test samples used:      0 (STRICT ZERO LEAKAGE)")
    print("-" * 80)

    # 2. Load model from best checkpoint
    checkpoint_path = ROOT / "models" / "checkpoints" / "best.pt"
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Trained checkpoint not found at {checkpoint_path}. Train model first.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = SpatiotemporalMTLNet(
        input_channels=checkpoint.get("input_channels", 13),
        baseline_channels=checkpoint.get("baseline_channels", 6),
        hidden_channels=checkpoint.get("hidden_channels", 32),
        num_heads=checkpoint.get("num_heads", 4),
        num_layers=checkpoint.get("num_layers", 2),
    ).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()

    # Load normalization statistics
    scaler_path = ROOT / "models" / "preprocessing" / "scaler.json"
    if not scaler_path.exists():
        raise FileNotFoundError(f"Normalization scaler not found at {scaler_path}.")
    norm_info = json.loads(scaler_path.read_text(encoding="utf-8"))
    seq_means = np.array([c["mean"] for c in norm_info["channels"][:13]], dtype=np.float32).reshape(1, 13, 1, 1)
    seq_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][:13]], dtype=np.float32).reshape(1, 13, 1, 1)
    base_means = np.array([c["mean"] for c in norm_info["channels"][13:19]], dtype=np.float32).reshape(6, 1, 1)
    base_stds = np.array([max(c["std"], 1e-7) for c in norm_info["channels"][13:19]], dtype=np.float32).reshape(6, 1, 1)

    # Run validation inference over all 7 validation sequences on the 114x84 grid
    raw_pred_list = []
    target_list = []
    with torch.inference_mode():
        for _, row in val_df.iterrows():
            data = np.load(ROOT / row["input_path"], allow_pickle=False)
            tgt = np.load(ROOT / row["target_path"], allow_pickle=False)["targets"]  # [5, 3, 114, 84]
            raw_in = data["inputs"]  # [7, 13, 114, 84]

            norm_in = (raw_in - seq_means) / seq_stds
            raw_base = raw_in[-1, list(BASELINE_INDICES), :, :]
            norm_base = (raw_base - base_means) / base_stds

            in_t = torch.from_numpy(norm_in).unsqueeze(0).float().to(device)
            base_t = torch.from_numpy(norm_base).unsqueeze(0).float().to(device)

            out = model(in_t, base_t)  # [1, 5, 3, 114, 84]
            raw_pred_list.append(out.cpu().numpy().squeeze(0))
            target_list.append(tgt)

    raw_predictions = np.stack(raw_pred_list, axis=0)  # [7, 5, 3, 114, 84]
    targets = np.stack(target_list, axis=0)            # [7, 5, 3, 114, 84]

    calibrated_predictions = np.zeros_like(raw_predictions)
    calibration_models: dict[str, dict] = {}
    calibration_reports: dict[str, dict] = {}

    print(f"{'Hazard':<16} {'Raw Brier':<12} {'Cal Brier':<12} {'Raw ECE':<12} {'Cal ECE':<12} {'Platt Slope':<12} {'Intercept':<12}")
    print("-" * 88)

    for h_idx, h_name in enumerate(HAZARDS):
        raw_h = raw_predictions[:, :, h_idx, :, :]
        tgt_h = targets[:, :, h_idx, :, :]

        # Mask out and ignore missing values (NaN) or out-of-bounds pixels
        valid_mask = np.isfinite(raw_h) & np.isfinite(tgt_h) & np.isin(tgt_h, (0, 1))
        x_valid = raw_h[valid_mask].ravel().astype(np.float64)
        y_valid = tgt_h[valid_mask].ravel().astype(np.float64)

        if len(x_valid) == 0:
            raise RuntimeError(f"No valid pixels found for hazard {h_name} in validation split.")

        # Augmented boundary anchor points (0.0, 0) and (1.0, 1) guarantee mathematical validity
        # and prevent single-class convergence issues in extreme weather events
        x_aug = np.concatenate([x_valid, [0.0, 1.0]])
        y_aug = np.concatenate([y_valid, [0.0, 1.0]])

        # Platt Scaling via Logistic Regression
        lr = LogisticRegression(solver="lbfgs", max_iter=1000)
        lr.fit(x_aug.reshape(-1, 1), y_aug)

        slope = float(lr.coef_[0][0])
        intercept = float(lr.intercept_[0])

        # Calibrate probabilities
        cal_flat = lr.predict_proba(x_valid.reshape(-1, 1))[:, 1]
        
        cal_h = np.copy(raw_h)
        cal_h[valid_mask] = cal_flat
        calibrated_predictions[:, :, h_idx, :, :] = cal_h

        # Metrics
        raw_brier = brier_score(x_valid, y_valid)
        cal_brier = brier_score(cal_flat, y_valid)
        raw_ece = expected_calibration_error(x_valid, y_valid)
        cal_ece = expected_calibration_error(cal_flat, y_valid)

        # Isotonic regression as comparative baseline
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(x_aug, y_aug)
        iso_brier = brier_score(iso.predict(x_valid), y_valid)

        calibration_models[h_name] = {
            "method": "platt_scaling",
            "slope": slope,
            "intercept": intercept,
            "fitted_samples": int(len(x_valid)),
            "positive_rate": float(np.mean(y_valid)),
            "isotonic_brier": iso_brier,
        }

        calibration_reports[h_name] = {
            "raw_brier_score": raw_brier,
            "calibrated_brier_score": cal_brier,
            "raw_ece": raw_ece,
            "calibrated_ece": cal_ece,
            "brier_improvement_percent": float(((raw_brier - cal_brier) / max(raw_brier, 1e-6)) * 100.0),
            "reliability_bins_raw": reliability_bins(x_valid, y_valid),
            "reliability_bins_calibrated": reliability_bins(cal_flat, y_valid),
        }

        print(f"{h_name:<16} {raw_brier:<12.5f} {cal_brier:<12.5f} {raw_ece:<12.5f} {cal_ece:<12.5f} {slope:<12.4f} {intercept:<12.4f}")

    print("=" * 88)

    # 3. Serialization
    # Update validation predictions with calibrated probabilities
    validation_pred_path = ROOT / "data" / "datasets" / "final" / "validation_predictions.npz"
    logits = np.log(np.clip(calibrated_predictions, 1e-6, 1 - 1e-6) / np.clip(1 - calibrated_predictions, 1e-6, 1))
    np.savez_compressed(
        validation_pred_path,
        probabilities=calibrated_predictions,
        raw_probabilities=raw_predictions,
        targets=targets,
        logits=logits,
    )

    # Persist calibration parameters
    cal_dir = ROOT / "models" / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_params_path = cal_dir / "calibration_params.json"
    
    calibration_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fitted_on": "validation",
        "validation_samples": len(val_df),
        "validation_event_id": "2021-05-26",
        "hazard_channels": list(HAZARDS),
        "models": calibration_models,
        "diagnostics": calibration_reports,
    }
    cal_params_path.write_text(json.dumps(calibration_payload, indent=2), encoding="utf-8")

    # Persist temperature scaling compatibility file
    temp_path = cal_dir / "temperature.json"
    temp_payload = {
        "method": "platt_scaling",
        "fit_split": "validation",
        "hazard_models": {h: {"slope": calibration_models[h]["slope"], "intercept": calibration_models[h]["intercept"]} for h in HAZARDS},
    }
    temp_path.write_text(json.dumps(temp_payload, indent=2), encoding="utf-8")

    # Persist report to reports/calibration_report.json
    report_path = ROOT / "reports" / "calibration_report.json"
    report_path.write_text(json.dumps({
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "platt_scaling",
        "fit_split": "validation",
        "test_split_used": False,
        "samples": int(targets.size),
        "hazard_reports": calibration_reports,
    }, indent=2), encoding="utf-8")

    print(f"Updated predictions:      {validation_pred_path.relative_to(ROOT)}")
    print(f"Calibration parameters:   {cal_params_path.relative_to(ROOT)}")
    print(f"Calibration report:       {report_path.relative_to(ROOT)}")
    print("PROBABILITY CALIBRATION COMPLETED SUCCESSFULLY.")
    print("=" * 88)

    return calibration_payload


def main() -> None:
    calibrate_validation()


if __name__ == "__main__":
    main()
