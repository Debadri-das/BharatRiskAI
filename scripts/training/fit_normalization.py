"""Fit spatiotemporal normalization parameters strictly on the training split."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reports.unified_feature_schema import BASELINE_ORDER, CHANNEL_ORDER

TARGET_HAZARDS = ["thunderstorm", "cloudburst", "flash_flood"]
EPSILON = 1e-7


def fit_normalization(index_path: Path | None = None) -> dict:
    if index_path is None:
        index_path = ROOT / "data" / "datasets" / "final" / "index.csv"

    if not index_path.exists():
        raise FileNotFoundError(f"Final dataset index not found at {index_path}. Build sequences first.")

    with index_path.open(encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))

    train_rows = [r for r in all_rows if r["split"] == "train"]
    val_rows = [r for r in all_rows if r["split"] == "validation"]
    test_rows = [r for r in all_rows if r["split"] == "test"]

    # 1. Strict Zero Data Leakage Verification
    if len(train_rows) != 6:
        raise ValueError(f"Strict constraint violated: expected exactly 6 training sequences, got {len(train_rows)}")
    
    unique_events = {r["event_id"] for r in train_rows}
    if unique_events != {"2020-05-20"}:
        raise ValueError(f"Strict constraint violated: training sequences must belong solely to Cyclone Amphan (2020-05-20), got {unique_events}")

    print("=" * 80)
    print("DATA NORMALIZATION STAGE: ZERO DATA LEAKAGE VERIFICATION")
    print("=" * 80)
    print(f"Total dataset samples in index:   {len(all_rows)}")
    print(f"Training sequences selected:      {len(train_rows)} (Cyclone Amphan, 2020-05-20)")
    print(f"Validation sequences skipped:     {len(val_rows)} (Cyclone Yaas, 2021-05-26 - STRICT ZERO LEAKAGE)")
    print(f"Test sequences skipped:           {len(test_rows)} (Cyclone Remal, 2024-05-26 - STRICT ZERO LEAKAGE)")
    print(f"Validation/Test sequences read:   0 (VERIFIED)")
    print("-" * 80)

    # 2. Channel-Wise Ingestion & Aggregation
    inputs_list = []
    targets_list = []
    for r in train_rows:
        npz_path = ROOT / r["input_path"]
        with np.load(npz_path, allow_pickle=False) as data:
            inp = data["inputs"]  # [7, 13, 114, 84]
            tgt = data["targets"] # [5, 3, 114, 84]
            assert inp.shape == (7, 13, 114, 84), f"Malformed input shape {inp.shape} in {npz_path}"
            assert tgt.shape == (5, 3, 114, 84), f"Malformed target shape {tgt.shape} in {npz_path}"
            assert np.isfinite(inp).all(), f"Non-finite input values in {npz_path}"
            assert np.isfinite(tgt).all(), f"Non-finite target values in {npz_path}"
            inputs_list.append(inp)
            targets_list.append(tgt)

    all_inputs = np.stack(inputs_list, axis=0)    # [6, 7, 13, 114, 84]
    all_targets = np.stack(targets_list, axis=0)  # [6, 5, 3, 114, 84]

    input_channel_stats = {}
    input_means = []
    input_stds = []
    input_mins = []
    input_maxs = []
    input_p99s = []

    print(f"{'Idx':<4} {'Input Channel':<16} {'Mean (mu)':<12} {'Std (sigma)':<12} {'Min':<10} {'Max':<10} {'99th %':<10}")
    print("-" * 80)

    for i, ch_name in enumerate(CHANNEL_ORDER):
        ch_vals = all_inputs[:, :, i, :, :].ravel().astype(np.float64)
        mu = float(ch_vals.mean())
        raw_sigma = float(ch_vals.std())
        sigma = float(max(raw_sigma, EPSILON))
        val_min = float(ch_vals.min())
        val_max = float(ch_vals.max())
        val_p99 = float(np.percentile(ch_vals, 99.0))

        input_means.append(mu)
        input_stds.append(sigma)
        input_mins.append(val_min)
        input_maxs.append(val_max)
        input_p99s.append(val_p99)

        input_channel_stats[ch_name] = {
            "index": i,
            "mean": mu,
            "std": sigma,
            "std_unclipped": raw_sigma,
            "min": val_min,
            "max": val_max,
            "percentile_99": val_p99,
            "epsilon_applied": raw_sigma < EPSILON,
        }

        print(f"{i:<4} {ch_name:<16} {mu:<12.5f} {sigma:<12.5f} {val_min:<10.3f} {val_max:<10.3f} {val_p99:<10.3f}")

    print("-" * 80)
    print(f"{'Idx':<4} {'Target Hazard':<16} {'Mean':<12} {'Std':<12} {'Min':<10} {'Max':<10} {'Pos Rate':<10}")
    print("-" * 80)

    target_channel_stats = {}
    target_means = []
    target_stds = []
    target_mins = []
    target_maxs = []
    target_pos_rates = []

    for j, h_name in enumerate(TARGET_HAZARDS):
        h_vals = all_targets[:, :, j, :, :].ravel().astype(np.float64)
        t_mu = float(h_vals.mean())
        raw_t_sigma = float(h_vals.std())
        t_sigma = float(max(raw_t_sigma, EPSILON))
        t_min = float(h_vals.min())
        t_max = float(h_vals.max())
        pos_rate = float((h_vals > 0.5).mean())

        target_means.append(t_mu)
        target_stds.append(t_sigma)
        target_mins.append(t_min)
        target_maxs.append(t_max)
        target_pos_rates.append(pos_rate)

        target_channel_stats[h_name] = {
            "index": j,
            "mean": t_mu,
            "std": t_sigma,
            "min": t_min,
            "max": t_max,
            "positive_rate": pos_rate,
        }

        print(f"{j:<4} {h_name:<16} {t_mu:<12.5f} {t_sigma:<12.5f} {t_min:<10.1f} {t_max:<10.1f} {pos_rate:<10.4f}")

    print("=" * 80)

    # 3. Serialization to JSON and NPZ
    generated_at = datetime.now(timezone.utc).isoformat()
    normalization_meta = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "training_cyclone_id": "2020-05-20",
        "training_sample_count": len(train_rows),
        "validation_sample_count_ingested": 0,
        "test_sample_count_ingested": 0,
        "temporal_frames": 7,
        "forecast_horizons": 5,
        "spatial_grid_shape": [114, 84],
        "epsilon": EPSILON,
        "input_channels": input_channel_stats,
        "target_channels": target_channel_stats,
    }

    datasets_dir = ROOT / "data" / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    stats_json_path = datasets_dir / "normalization_stats.json"
    stats_npz_path = datasets_dir / "normalization_stats.npz"

    with stats_json_path.open("w", encoding="utf-8") as f:
        json.dump(normalization_meta, f, indent=2)

    np.savez_compressed(
        stats_npz_path,
        input_mean=np.array(input_means, dtype=np.float32),
        input_std=np.array(input_stds, dtype=np.float32),
        input_min=np.array(input_mins, dtype=np.float32),
        input_max=np.array(input_maxs, dtype=np.float32),
        input_p99=np.array(input_p99s, dtype=np.float32),
        target_mean=np.array(target_means, dtype=np.float32),
        target_std=np.array(target_stds, dtype=np.float32),
        channel_names=np.array(CHANNEL_ORDER),
        target_names=np.array(TARGET_HAZARDS),
    )

    # Backward compatibility with legacy scaler.json
    scaler_dir = ROOT / "models" / "preprocessing"
    scaler_dir.mkdir(parents=True, exist_ok=True)
    scaler_path = scaler_dir / "scaler.json"
    legacy_scaler = {
        "method": "training-only per-channel standardization",
        "channels": [
            {"name": ch, "mean": input_channel_stats[ch]["mean"], "std": input_channel_stats[ch]["std"]}
            for ch in CHANNEL_ORDER
        ] + [
            {"name": f"baseline_{ch}", "mean": input_channel_stats[ch]["mean"], "std": input_channel_stats[ch]["std"]}
            for ch in BASELINE_ORDER
        ],
    }
    with scaler_path.open("w", encoding="utf-8") as f:
        json.dump(legacy_scaler, f, indent=2)

    print(f"Serialized JSON metrics:  {stats_json_path.relative_to(ROOT)}")
    print(f"Serialized NPZ tensors:   {stats_npz_path.relative_to(ROOT)}")
    print(f"Legacy model scaler:      {scaler_path.relative_to(ROOT)}")
    print("NORMALIZATION STAGE COMPLETED SUCCESSFULLY.")
    print("=" * 80)

    return normalization_meta


if __name__ == "__main__":
    fit_normalization()
