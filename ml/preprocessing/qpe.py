"""Coverage-aware QPE rate and accumulation calculations.

Calculates temporal rainfall accumulation from instantaneous rain rates:
    R_1h = sum_{i=1}^2  r_i * Delta t_i   (1 hour,  2 steps at 30-min interval)
    R_3h = sum_{i=1}^6  r_i * Delta t_i   (3 hours, 6 steps at 30-min interval)
    R_6h = sum_{i=1}^{12} r_i * Delta t_i  (6 hours, 12 steps at 30-min interval)

Coverage-aware: only calculate an accumulation when temporal coverage is sufficient.
Missing observations and interval gaps remain NaN and are never treated as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np


@dataclass(frozen=True)
class Accumulation:
    value: np.ndarray
    coverage: np.ndarray
    status: str


def accumulate_rate(
    rates_mm_per_hour: np.ndarray,
    times: list[datetime],
    window_hours: float,
    *,
    minimum_coverage: float = 0.9,
    max_gap_hours: float = 0.75,
) -> Accumulation:
    """Integrate rainfall rate over actual observation intervals.

    Insufficient temporal coverage or missing intervals remain NaN.
    
    Args:
        rates_mm_per_hour: Array of rain rates [T, H, W] or [T, ...].
        times: List of strictly increasing observation datetimes corresponding to axis 0.
        window_hours: Accumulation window in hours (e.g. 1.0, 3.0, 6.0).
        minimum_coverage: Fraction of window required to be validly observed (default 0.9).
        max_gap_hours: Maximum allowable interval between successive observations before
                       it is flagged as an unobserved gap (default 0.75h = 45 min for 30m data).
    """
    rates = np.asarray(rates_mm_per_hour, dtype=np.float64)
    if rates.ndim < 1 or rates.shape[0] != len(times):
        raise ValueError("rates first dimension must match timestamps")
    if window_hours <= 0 or not 0 < minimum_coverage <= 1:
        raise ValueError("window_hours and minimum_coverage must be positive")
    if len(times) < 2:
        shape = rates.shape[1:]
        return Accumulation(np.full(shape, np.nan, dtype=np.float32), np.zeros(shape, dtype=np.float32), "INSUFFICIENT_COVERAGE")

    order = np.argsort([item.timestamp() for item in times])
    sorted_times = [times[int(i)] for i in order]
    if len({item for item in sorted_times}) != len(sorted_times):
        raise ValueError("duplicate QPE timestamps are not valid input")
    sorted_rates = rates[order]

    # Target accumulation for the final timestamp in the series
    end = len(sorted_times) - 1
    target_time = sorted_times[end]
    window_start = target_time - timedelta(hours=window_hours)

    spatial_shape = rates.shape[1:]
    total = np.zeros(spatial_shape, dtype=np.float64)
    covered = np.zeros(spatial_shape, dtype=np.float64)

    for index in range(1, end + 1):
        t_prev = sorted_times[index - 1]
        t_curr = sorted_times[index]
        interval = (t_curr - t_prev).total_seconds() / 3600.0

        if interval <= 0:
            raise ValueError("QPE timestamps must be strictly increasing")
        
        # Check if this interval overlaps with [window_start, target_time]
        if t_curr <= window_start:
            continue
            
        # If the gap between successive observations is too large, it cannot be assumed
        # to have sustained the current rain rate
        if interval > max_gap_hours:
            continue

        effective_interval = interval
        if t_prev < window_start:
            effective_interval = (t_curr - window_start).total_seconds() / 3600.0

        valid = np.isfinite(sorted_rates[index])
        total = np.where(valid, total + sorted_rates[index] * effective_interval, total)
        covered = np.where(valid, covered + effective_interval, covered)

    required_coverage_hours = window_hours * minimum_coverage
    result = np.where(covered >= required_coverage_hours, total, np.nan).astype(np.float32)
    coverage_fraction = np.clip(covered / window_hours, 0.0, 1.0).astype(np.float32)

    status = "ACCEPTED" if np.any(np.isfinite(result)) else "INSUFFICIENT_COVERAGE"
    return Accumulation(result, coverage_fraction, status)
