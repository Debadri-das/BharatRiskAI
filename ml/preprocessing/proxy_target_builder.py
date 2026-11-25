"""Future-observation satellite-derived proxy targets.

Important Scientific Distinction:
A model trained to predict future heavy rainfall is an extreme rainfall proxy classifier,
NOT automatically a flood prediction model. For a genuine flood classifier, the target
must be verified flood occurrence or inundation (e.g. gauge observations, Sentinel-1 SAR
inundation maps, or authoritative disaster damage reports), not simply high future QPE.

These targets are not ground truth and are never generated from issue-time features.
Missing future observations are excluded, not treated as negatives.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProxyTargetConfig:
    horizon_hours: float = 6.0
    threshold_mm: float = 50.0
    window_hours: float = 3.0
    version: str = "qpe-future-accumulation-v2"
    cadence_minutes: int = 30
    min_coverage_fraction: float = 1.0

    @property
    def definition(self) -> str:
        return (
            f"future rolling {self.window_hours:g}-h QPE accumulation >= {self.threshold_mm:g} mm "
            f"within {self.horizon_hours:g} h (extreme rainfall proxy; NOT confirmed flood inundation)"
        )

    @property
    def scientific_note(self) -> str:
        return (
            "A model trained to predict future heavy rainfall is an extreme rainfall proxy classifier, "
            "not automatically a flood prediction model. For a genuine flood classifier, its target must be "
            "verified flood occurrence or inundation, not simply high future QPE."
        )


def compute_rolling_accumulations(
    observations: pd.DataFrame,
    windows_hours: Sequence[float] = (1.0, 3.0, 6.0),
    cadence_minutes: int = 30,
    time_col: str = "qpe_time",
    id_col: str = "grid_id",
    rate_col: str = "qpe_rate_mm_hr",
    accum_col: str = "qpe_accumulation_mm",
) -> pd.DataFrame:
    """Compute rolling 1-h, 3-h, and 6-h rainfall accumulations per grid cell with gap checking.
    
    Ensures that missing intervals or temporal gaps (>0.75h) result in NaN accumulation
    rather than being zero-filled or treated as continuous.
    """
    df = observations.copy()
    if time_col not in df.columns:
        raise ValueError(f"Missing time column '{time_col}' in observations")
    if id_col not in df.columns:
        df[id_col] = "__default__"

    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.sort_values([id_col, time_col]).reset_index(drop=True)

    has_rate = rate_col in df.columns
    has_accum = accum_col in df.columns
    if not has_rate and not has_accum:
        raise ValueError(f"Observations must contain either '{rate_col}' or '{accum_col}'")

    dt_hours = cadence_minutes / 60.0
    max_gap_seconds = int((dt_hours + 0.25) * 3600)  # e.g. 45 min for nominal 30-min cadence

    for w_h in windows_hours:
        col_name = f"qpe_rolling_{int(w_h)}h_mm" if float(w_h).is_integer() else f"qpe_rolling_{w_h:g}h_mm"
        expected_steps = int(round(w_h / dt_hours))

        rolling_vals = []
        for _, group in df.groupby(id_col, sort=False):
            times = group[time_col].values
            values = group[rate_col].values if has_rate else group[accum_col].values
            n = len(group)
            cell_accum = np.full(n, np.nan, dtype=np.float64)

            for i in range(n):
                if i + 1 < expected_steps:
                    continue
                w_slice = slice(i - expected_steps + 1, i + 1)
                w_times = times[w_slice]
                w_vals = values[w_slice]

                # Strict check: any NaN in the rolling window invalidates the accumulation
                if not np.isfinite(w_vals).all():
                    continue

                # Strict check: temporal continuity (no missing scans/gaps)
                time_diffs_sec = (w_times[1:] - w_times[:-1]).astype("timedelta64[s]").astype(np.int64)
                if len(time_diffs_sec) > 0 and (time_diffs_sec > max_gap_seconds).any():
                    continue

                # Accumulate: if rate (mm/h), multiply by dt_hours; if interval rain, sum directly
                if has_rate:
                    cell_accum[i] = float(np.sum(w_vals) * dt_hours)
                else:
                    cell_accum[i] = float(np.sum(w_vals))

            rolling_vals.extend(cell_accum)

        df[col_name] = rolling_vals

    return df


def build_future_qpe_targets(
    observations: pd.DataFrame,
    config: ProxyTargetConfig = ProxyTargetConfig(),
    cadence_minutes: int = 30,
) -> pd.DataFrame:
    """Construct future rolling rainfall proxy targets separately for each grid cell.
    
    Strict constraints:
    1. Grid cell spatial identification via 'grid_id'.
    2. Multiple spatial observations at the same issue timestamp are permitted.
    3. Rolling window accumulation (e.g. 3-h) is constructed across successive future observations.
    4. Complete future observation coverage is verified; missing future observations are excluded as NaN.
    """
    has_accum = "qpe_accumulation_mm" in observations.columns
    has_rate = "qpe_rate_mm_hr" in observations.columns
    if not has_accum and not has_rate:
        raise ValueError("Observations must contain either 'qpe_accumulation_mm' or 'qpe_rate_mm_hr'")

    required = {"issue_time", "qpe_time"}
    missing = required - set(observations.columns)
    if missing:
        raise ValueError(f"Missing target columns: {sorted(missing)}")

    frame = observations.copy()
    if "grid_id" not in frame.columns:
        frame["grid_id"] = "__default__"

    frame["issue_time"] = pd.to_datetime(frame["issue_time"], utc=True)
    frame["qpe_time"] = pd.to_datetime(frame["qpe_time"], utc=True)

    dt_hours = cadence_minutes / 60.0
    expected_window_steps = max(1, int(round(config.window_hours / dt_hours)))

    rows = []
    for (issue_time, grid_id), group in frame.groupby(["issue_time", "grid_id"], sort=True):
        future_end = issue_time + pd.Timedelta(hours=config.horizon_hours)
        future = group[(group["qpe_time"] > issue_time) & (group["qpe_time"] <= future_end)].sort_values("qpe_time")

        val_col = "qpe_accumulation_mm" if has_accum else "qpe_rate_mm_hr"
        valid = future[val_col].notna() & np.isfinite(future[val_col])
        coverage = float(valid.mean()) if len(future) else 0.0

        if not len(future) or not valid.all():
            target, confidence, status = np.nan, 0.0, "UNUSABLE_MISSING_FUTURE"
        else:
            # Case 1: Multiple successive observations in future window -> construct actual rolling accumulation
            if len(future) > 1 and (has_rate or f"qpe_rolling_{int(config.window_hours)}h_mm" in future.columns):
                # If pre-computed rolling column exists
                rolling_col = f"qpe_rolling_{int(config.window_hours)}h_mm"
                if rolling_col in future.columns and future[rolling_col].notna().any():
                    rolling_series = future[rolling_col].dropna()
                    max_accum = float(rolling_series.max()) if len(rolling_series) else np.nan
                else:
                    # Construct rolling accumulation from rates or interval accumulations
                    rates = future[val_col].values
                    times = future["qpe_time"].values
                    max_accum = -np.inf
                    has_valid_window = False

                    for idx in range(len(future)):
                        if idx + 1 >= expected_window_steps:
                            w_slice = slice(idx - expected_window_steps + 1, idx + 1)
                            w_times = times[w_slice]
                            w_vals = rates[w_slice]
                            # Check gap between steps <= 0.75h
                            time_diffs_sec = (w_times[1:] - w_times[:-1]).astype("timedelta64[s]").astype(np.int64)
                            if len(time_diffs_sec) == 0 or (time_diffs_sec <= 2700).all():
                                accum = float(np.sum(w_vals) * dt_hours if has_rate else np.sum(w_vals))
                                max_accum = max(max_accum, accum)
                                has_valid_window = True

                    max_accum = max_accum if has_valid_window else np.nan

                if np.isnan(max_accum):
                    target, confidence, status = np.nan, 0.0, "UNUSABLE_MISSING_FUTURE"
                else:
                    target = float(max_accum >= config.threshold_mm)
                    confidence, status = coverage, "ACCEPTED"

            # Case 2: Discrete summary accumulation records provided directly
            else:
                target = float((future[val_col] >= config.threshold_mm).any())
                confidence, status = coverage, "ACCEPTED"

        rows.append({
            "issue_time": issue_time,
            "grid_id": grid_id,
            "target": target,
            "target_type": "binary_proxy",
            "target_nature": "heavy_rainfall_proxy",
            "target_definition": config.definition,
            "target_source": "INSAT-3DR HEM QPE",
            "target_horizon": f"{config.horizon_hours:g}h",
            "target_window": f"{config.window_hours:g}h",
            "target_threshold_mm": config.threshold_mm,
            "target_confidence": confidence,
            "target_coverage": coverage,
            "target_version": config.version,
            "target_status": status,
            "scientific_disclaimer": config.scientific_note,
        })

    return pd.DataFrame(rows)


def assert_future_only(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    """Validate that features and targets are uniquely identified by (issue_time, grid_id).
    
    Multiple spatial grid cells at the same issue timestamp are permitted.
    Duplicate (issue_time, grid_id) composite pairs are strictly prohibited.
    """
    required = {"issue_time", "grid_id"}
    if not required.issubset(features.columns) or not required.issubset(targets.columns):
        raise ValueError("features and targets require 'issue_time' and 'grid_id'")
    if features.duplicated(["issue_time", "grid_id"]).any():
        raise ValueError("duplicate (issue_time, grid_id) feature rows are not allowed")
    if targets.duplicated(["issue_time", "grid_id"]).any():
        raise ValueError("duplicate (issue_time, grid_id) target rows are not allowed")
