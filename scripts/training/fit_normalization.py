"""Fit spatiotemporal normalization parameters strictly on the training split.

Section 1.3 Production Implementation:
1. Read the training split only (strict zero data leakage from validation or test).
2. Calculate per-channel statistics (mean, std, min, max, p99, valid counts).
3. Exclude invalid pixels (NaNs, infinities, non-binary targets) from statistics.
4. Save missingness masks (per-sample input and target masks + dataset-level spatial missingness maps).
5. Apply the exact same training statistics to validation and test.
6. Never fit normalization statistics using validation or test observations.
7. Ensure static DEM channels (elevation, slope, drainage) are evaluated on the unique
   static terrain grid once, NOT counted as independent new observations every 30 minutes.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reports.unified_feature_schema import BASELINE_ORDER, CHANNEL_ORDER

TARGET_HAZARDS = ["thunderstorm", "cloudburst", "flash_flood"]
STATIC_DEM_CHANNELS = {"elevation", "slope", "drainage"}
EPSILON = 1e-7


def _resolve_sample_path(rel_or_abs: str | Path, base_root: Path, index_dir: Path) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute() and p.exists():
        return p
    for cand in [base_root / p, index_dir / p, index_dir.parent / p]:
        if cand.exists():
            return cand
    return base_root / p


def fit_normalization(
    index_path: Path | None = None,
    output_dir: Path | None = None,
    apply_to_splits: bool = True,
) -> dict:
    """Fit per-channel normalization statistics strictly on the training split."""
    if index_path is None:
        index_path = ROOT / "data" / "datasets" / "final" / "index.csv"

    index_path = Path(index_path)
    if not index_path.exists():
        raise FileNotFoundError(f"Dataset index not found at {index_path}. Build sequences first.")

    index_dir = index_path.parent
    base_root = ROOT

    with index_path.open(encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))

    train_rows = [r for r in all_rows if r["split"] == "train"]
    val_rows = [r for r in all_rows if r["split"] in ("validation", "val")]
    test_rows = [r for r in all_rows if r["split"] == "test"]

    if not train_rows:
        raise ValueError("No training sequences are available for normalization.")

    train_events = sorted({r.get("event_id", "unassigned") for r in train_rows})
    val_events = sorted({r.get("event_id", "unassigned") for r in val_rows})
    test_events = sorted({r.get("event_id", "unassigned") for r in test_rows})

    # Strict Zero Event Leakage verification
    overlap_val = set(train_events) & set(val_events)
    overlap_test = set(train_events) & set(test_events)
    if overlap_val or overlap_test:
        raise ValueError(
            f"Event leakage detected! Training events overlap with validation ({overlap_val}) or test ({overlap_test}). "
            f"All frames belonging to one storm event must remain strictly in one split."
        )

    print("=" * 80)
    print("DATA NORMALIZATION STAGE: TRAINING-ONLY SPATIOTEMPORAL FITTING")
    print("=" * 80)
    print(f"Total dataset samples in index:   {len(all_rows)}")
    print(f"Training sequences selected:      {len(train_rows)} across {len(train_events)} event(s): {train_events}")
    print(f"Validation sequences skipped:     {len(val_rows)} across {len(val_events)} event(s) (STRICT ZERO LEAKAGE)")
    print(f"Test sequences skipped:           {len(test_rows)} across {len(test_events)} event(s) (STRICT ZERO LEAKAGE)")
    print(f"Validation/Test sequences read:   0 (VERIFIED for parameter fitting)")
    print("-" * 80)

    # Accumulators for dynamic time-varying channels
    dynamic_indices = [i for i, ch in enumerate(CHANNEL_ORDER) if ch not in STATIC_DEM_CHANNELS]
    dem_indices = [i for i, ch in enumerate(CHANNEL_ORDER) if ch in STATIC_DEM_CHANNELS]

    num_channels = len(CHANNEL_ORDER)
    ch_counts = np.zeros(num_channels, dtype=np.int64)
    ch_sums = np.zeros(num_channels, dtype=np.float64)
    ch_sum_sqs = np.zeros(num_channels, dtype=np.float64)
    ch_mins = np.full(num_channels, np.inf, dtype=np.float64)
    ch_maxs = np.full(num_channels, -np.inf, dtype=np.float64)
    ch_samples: dict[int, list[np.ndarray]] = {i: [] for i in range(num_channels)}

    num_targets = len(TARGET_HAZARDS)
    tgt_counts = np.zeros(num_targets, dtype=np.int64)
    tgt_sums = np.zeros(num_targets, dtype=np.float64)
    tgt_sum_sqs = np.zeros(num_targets, dtype=np.float64)
    tgt_mins = np.full(num_targets, np.inf, dtype=np.float64)
    tgt_maxs = np.full(num_targets, -np.inf, dtype=np.float64)
    tgt_pos_counts = np.zeros(num_targets, dtype=np.int64)

    spatial_shape: tuple[int, int] | None = None
    total_input_frames = 0
    total_target_frames = 0
    ch_missing_map: np.ndarray | None = None
    tgt_missing_map: np.ndarray | None = None

    first_dem_slice: dict[int, np.ndarray] = {}

    # Stream through training rows to support 180-day large-scale datasets without OOM
    for r in train_rows:
        npz_path = _resolve_sample_path(r["input_path"], base_root, index_dir)
        with np.load(npz_path, allow_pickle=False) as data:
            inp = data["inputs"]   # Expected shape [7, 13, H, W]
            tgt = data["targets"]  # Expected shape [5, 3, H, W]

            if inp.ndim != 4 or inp.shape[1] != num_channels:
                raise ValueError(f"Malformed input shape {inp.shape} in {npz_path}; expected [7, {num_channels}, H, W]")
            if tgt.ndim != 4 or tgt.shape[1] != num_targets:
                raise ValueError(f"Malformed target shape {tgt.shape} in {npz_path}; expected [5, {num_targets}, H, W]")

            current_shape = (int(inp.shape[-2]), int(inp.shape[-1]))
            if spatial_shape is None:
                spatial_shape = current_shape
                ch_missing_map = np.zeros((num_channels, spatial_shape[0], spatial_shape[1]), dtype=np.int64)
                tgt_missing_map = np.zeros((num_targets, spatial_shape[0], spatial_shape[1]), dtype=np.int64)
            elif spatial_shape != current_shape:
                raise ValueError(f"Spatial dimension mismatch: sequence {npz_path} has shape {current_shape}, expected {spatial_shape}")

            total_input_frames += inp.shape[0]
            total_target_frames += tgt.shape[0]

            # 1. Accumulate time-varying channels (exclude invalid / NaN pixels)
            for c in dynamic_indices:
                vals = inp[:, c, :, :]
                vmask = np.isfinite(vals)
                ch_missing_map[c] += np.sum(~vmask, axis=0)

                valid_v = vals[vmask].astype(np.float64)
                if valid_v.size > 0:
                    ch_counts[c] += valid_v.size
                    ch_sums[c] += float(np.sum(valid_v))
                    ch_sum_sqs[c] += float(np.sum(valid_v ** 2))
                    ch_mins[c] = min(ch_mins[c], float(np.min(valid_v)))
                    ch_maxs[c] = max(ch_maxs[c], float(np.max(valid_v)))

                    # Keep a sample reservoir for 99th percentile calculation
                    if sum(s.size for s in ch_samples[c]) < 50000:
                        n_sample = min(valid_v.size, 1000)
                        sub = np.random.choice(valid_v, size=n_sample, replace=False) if valid_v.size > n_sample else valid_v
                        ch_samples[c].append(sub)

            # Store first encountered 2D slice for static DEM channels
            for c in dem_indices:
                if c not in first_dem_slice:
                    first_dem_slice[c] = inp[0, c, :, :].copy()

            # 2. Accumulate target channels (exclude invalid / NaN target pixels)
            for j in range(num_targets):
                tvals = tgt[:, j, :, :]
                tvmask = np.isfinite(tvals) & np.isin(tvals, [0.0, 1.0, 0, 1])
                tgt_missing_map[j] += np.sum(~np.isfinite(tvals), axis=0)

                valid_t = tvals[tvmask].astype(np.float64)
                if valid_t.size > 0:
                    tgt_counts[j] += valid_t.size
                    tgt_sums[j] += float(np.sum(valid_t))
                    tgt_sum_sqs[j] += float(np.sum(valid_t ** 2))
                    tgt_mins[j] = min(tgt_mins[j], float(np.min(valid_t)))
                    tgt_maxs[j] = max(tgt_maxs[j], float(np.max(valid_t)))
                    tgt_pos_counts[j] += int(np.sum(valid_t > 0.5))

    # 3. Static DEM Channels: evaluate on unique spatial domain once
    # Prevent static DEM channels from being counted as independent new terrain observations every 30 minutes!
    dem_features_path = base_root / "data" / "derived" / "terrain" / "dem_features.npz"
    dem_source_data = None
    if dem_features_path.exists():
        try:
            dem_source_data = np.load(dem_features_path, allow_pickle=False)
        except Exception:
            dem_source_data = None

    for c in dem_indices:
        ch_name = CHANNEL_ORDER[c]
        if dem_source_data is not None and ch_name in dem_source_data:
            static_grid = dem_source_data[ch_name].astype(np.float32)
        elif c in first_dem_slice:
            static_grid = first_dem_slice[c]
        else:
            raise ValueError(f"Static DEM channel {ch_name} could not be extracted.")

        vmask = np.isfinite(static_grid)
        valid_dem = static_grid[vmask].astype(np.float64)
        if valid_dem.size == 0:
            raise ValueError(f"Static DEM channel {ch_name} has no valid pixels in the terrain grid.")

        ch_counts[c] = valid_dem.size
        ch_sums[c] = float(np.sum(valid_dem))
        ch_sum_sqs[c] = float(np.sum(valid_dem ** 2))
        ch_mins[c] = float(np.min(valid_dem))
        ch_maxs[c] = float(np.max(valid_dem))
        ch_samples[c] = [valid_dem]
        ch_missing_map[c] = (~vmask).astype(np.int64) * total_input_frames

    if dem_source_data is not None:
        dem_source_data.close()

    # 4. Compute per-channel statistics
    input_channel_stats = {}
    input_means = []
    input_stds = []
    input_mins = []
    input_maxs = []
    input_p99s = []

    print(f"{'Idx':<4} {'Input Channel':<16} {'Mean (mu)':<12} {'Std (sigma)':<12} {'Min':<10} {'Max':<10} {'99th %':<10} {'Valid Px':<10}")
    print("-" * 92)

    for i, ch_name in enumerate(CHANNEL_ORDER):
        if ch_counts[i] == 0:
            raise ValueError(f"Training channel {ch_name} has no valid observations in training split.")

        mu = float(ch_sums[i] / ch_counts[i])
        var = max(float(ch_sum_sqs[i] / ch_counts[i] - mu ** 2), 0.0)
        raw_sigma = float(np.sqrt(var))
        sigma = float(max(raw_sigma, EPSILON))
        val_min = float(ch_mins[i])
        val_max = float(ch_maxs[i])

        if ch_samples[i]:
            all_sampled = np.concatenate(ch_samples[i])
            val_p99 = float(np.percentile(all_sampled, 99.0))
        else:
            val_p99 = val_max

        is_dem = ch_name in STATIC_DEM_CHANNELS
        denom_pixels = (spatial_shape[0] * spatial_shape[1]) if is_dem else (total_input_frames * spatial_shape[0] * spatial_shape[1])
        missing_frac = float(max(0.0, 1.0 - (ch_counts[i] / max(denom_pixels, 1))))

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
            "valid_pixel_count": int(ch_counts[i]),
            "missing_fraction": missing_frac,
            "is_static_dem": is_dem,
            "observation_cadence": "static_spatial_grid_once" if is_dem else "temporal_30min_accumulated",
            "epsilon_applied": raw_sigma < EPSILON,
        }

        tag = " (DEM static)" if is_dem else ""
        print(f"{i:<4} {ch_name + tag:<16} {mu:<12.5f} {sigma:<12.5f} {val_min:<10.3f} {val_max:<10.3f} {val_p99:<10.3f} {ch_counts[i]:<10}")

    print("-" * 92)
    print(f"{'Idx':<4} {'Target Hazard':<16} {'Mean':<12} {'Std':<12} {'Min':<10} {'Max':<10} {'Pos Rate':<10} {'Valid Px':<10}")
    print("-" * 92)

    target_channel_stats = {}
    target_means = []
    target_stds = []
    target_mins = []
    target_maxs = []
    target_pos_rates = []

    for j, h_name in enumerate(TARGET_HAZARDS):
        if tgt_counts[j] == 0:
            # Handle hazard targets with all missing values gracefully
            t_mu, t_sigma, t_min, t_max, pos_rate, missing_frac = 0.0, 1.0, 0.0, 0.0, 0.0, 1.0
        else:
            t_mu = float(tgt_sums[j] / tgt_counts[j])
            t_var = max(float(tgt_sum_sqs[j] / tgt_counts[j] - t_mu ** 2), 0.0)
            t_sigma = float(max(np.sqrt(t_var), EPSILON))
            t_min = float(tgt_mins[j])
            t_max = float(tgt_maxs[j])
            pos_rate = float(tgt_pos_counts[j] / tgt_counts[j])
            total_possible_tgt = total_target_frames * spatial_shape[0] * spatial_shape[1]
            missing_frac = float(max(0.0, 1.0 - (tgt_counts[j] / max(total_possible_tgt, 1))))

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
            "valid_pixel_count": int(tgt_counts[j]),
            "missing_fraction": missing_frac,
        }

        print(f"{j:<4} {h_name:<16} {t_mu:<12.5f} {t_sigma:<12.5f} {t_min:<10.1f} {t_max:<10.1f} {pos_rate:<10.4f} {tgt_counts[j]:<10}")

    print("=" * 92)

    # 5. Serialization to JSON and NPZ
    generated_at = datetime.now(timezone.utc).isoformat()
    normalization_meta = {
        "schema_version": "2.0",
        "generated_at": generated_at,
        "training_event_ids": train_events,
        "training_sample_count": len(train_rows),
        "validation_sample_count_ingested": len(val_rows),
        "test_sample_count_ingested": len(test_rows),
        "temporal_frames": 7,
        "forecast_horizons": 5,
        "spatial_grid_shape": list(spatial_shape) if spatial_shape else [114, 84],
        "epsilon": EPSILON,
        "input_channels": input_channel_stats,
        "target_channels": target_channel_stats,
        "leakage_verification": {
            "validation_samples_used_in_fitting": 0,
            "test_samples_used_in_fitting": 0,
            "status": "STRICT ZERO LEAKAGE VERIFIED",
        },
    }

    datasets_dir = base_root / "data" / "datasets" if output_dir is None else Path(output_dir)
    datasets_dir.mkdir(parents=True, exist_ok=True)
    stats_json_path = datasets_dir / "normalization_stats.json"
    stats_npz_path = datasets_dir / "normalization_stats.npz"

    with stats_json_path.open("w", encoding="utf-8") as f:
        json.dump(normalization_meta, f, indent=2)

    # Missing frequency spatial maps
    input_missing_freq = (ch_missing_map / max(total_input_frames, 1)).astype(np.float32)
    target_missing_freq = (tgt_missing_map / max(total_target_frames, 1)).astype(np.float32)

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
        input_missing_frequency=input_missing_freq,
        target_missing_frequency=target_missing_freq,
    )

    # Legacy scaler.json for inference compatibility
    scaler_dir = base_root / "models" / "preprocessing"
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

    print(f"Serialized JSON metrics:  {stats_json_path}")
    print(f"Serialized NPZ tensors:   {stats_npz_path}")
    print(f"Legacy model scaler:      {scaler_path}")

    # 6. Apply training normalization to all splits & save missingness masks
    if apply_to_splits and len(all_rows) > 0:
        apply_normalization_to_splits(
            all_rows=all_rows,
            seq_means=np.array(input_means, dtype=np.float32),
            seq_stds=np.array(input_stds, dtype=np.float32),
            base_root=base_root,
            index_dir=index_dir,
            output_dir=datasets_dir,
        )

    print("NORMALIZATION STAGE COMPLETED SUCCESSFULLY.")
    print("=" * 80)

    return normalization_meta


def apply_normalization_to_splits(
    all_rows: list[dict[str, Any]],
    seq_means: np.ndarray,
    seq_stds: np.ndarray,
    base_root: Path,
    index_dir: Path,
    output_dir: Path,
) -> dict[str, int]:
    """Apply training statistics strictly to all splits and save missingness masks."""
    masks_dir = output_dir / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    normalized_dir = output_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    counts = {"train": 0, "validation": 0, "test": 0}
    seq_m = seq_means.reshape(1, len(seq_means), 1, 1)
    seq_s = seq_stds.reshape(1, len(seq_stds), 1, 1)

    print(f"Applying training-only normalization and saving missingness masks across {len(all_rows)} samples...")

    for r in all_rows:
        split = r.get("split", "train")
        counts[split] = counts.get(split, 0) + 1
        npz_path = _resolve_sample_path(r["input_path"], base_root, index_dir)
        stem = npz_path.stem

        with np.load(npz_path, allow_pickle=False) as data:
            raw_inp = data["inputs"]
            raw_tgt = data["targets"]
            ts = str(data["timestamp"]) if "timestamp" in data else r.get("timestamp", "")

        # Missingness & validity masks
        input_missing_mask = ~np.isfinite(raw_inp)
        input_valid_mask = np.isfinite(raw_inp)
        target_missing_mask = ~np.isfinite(raw_tgt)
        target_valid_mask = np.isfinite(raw_tgt) & np.isin(raw_tgt, [0.0, 1.0, 0, 1])

        # Standardize using training statistics; impute missing with 0.0 (standardized training mean)
        norm_inputs = np.where(input_valid_mask, (raw_inp - seq_m) / seq_s, 0.0).astype(np.float32)

        # 1. Save dedicated missingness masks
        mask_file = masks_dir / f"{stem}_mask.npz"
        np.savez_compressed(
            mask_file,
            input_missing_mask=input_missing_mask,
            input_valid_mask=input_valid_mask,
            target_missing_mask=target_missing_mask,
            target_valid_mask=target_valid_mask,
            timestamp=ts,
            split=split,
        )

        # 2. Save normalized sample
        norm_file = normalized_dir / f"{stem}.npz"
        np.savez_compressed(
            norm_file,
            inputs=norm_inputs,
            raw_inputs=raw_inp,
            targets=raw_tgt,
            input_missing_mask=input_missing_mask,
            target_missing_mask=target_missing_mask,
            timestamp=ts,
            split=split,
        )

        # 3. Update the sequence file in-place with missingness masks for frictionless downstream access
        try:
            np.savez_compressed(
                npz_path,
                inputs=raw_inp,
                targets=raw_tgt,
                timestamp=ts,
                input_missing_mask=input_missing_mask,
                input_valid_mask=input_valid_mask,
                target_missing_mask=target_missing_mask,
                target_valid_mask=target_valid_mask,
            )
        except Exception:
            pass

    print(f"Masks and normalized samples saved for {counts['train']} train, {counts.get('validation', 0)} val, {counts.get('test', 0)} test.")
    return counts


if __name__ == "__main__":
    fit_normalization()
