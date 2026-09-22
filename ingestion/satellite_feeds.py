"""Satellite observation bundle loading and optional provider refresh.

MOSDAC distributes products through account-specific services, so endpoint URLs are
configuration rather than assumptions in code. Downloaded products are decoded by
``real_data`` and then reduced to model-ready zone observations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from backend.config.settings import get_settings
from ingestion.real_data import latest_file, read_imdaa, read_insat


def _mean(value: Any, default: float) -> float:
    values = np.asarray(value, dtype=float)
    finite = values[np.isfinite(values)]
    return round(float(finite.mean()), 3) if finite.size else default


def latest_satellite_observation() -> dict[str, Any]:
    """Return the newest decoded INSAT and IMDAA signals available locally.

    The worker should refresh the configured MOSDAC/IMDAA endpoints before this
    function runs. Missing products are reported explicitly so stale sample data
    cannot be presented as a live alert feed.
    """
    settings = get_settings()
    insat_path = latest_file(settings.insat_data_dir, (".nc", ".nc4", ".netcdf", ".h5", ".hdf5"))
    imdaa_path = latest_file(settings.imdaa_data_dir, (".nc", ".nc4", ".netcdf"))
    if not insat_path:
        raise FileNotFoundError("Missing satellite products: INSAT-3D")

    insat = read_insat(insat_path)
    imdaa = read_imdaa(imdaa_path) if imdaa_path else {}
    qpe = _mean(insat.get("qpe"), 0.0)
    ctt = _mean(insat.get("ctt"), float("nan"))
    iwv = _mean(imdaa.get("iwv"), float("nan"))
    temperature = _mean(imdaa.get("temperature"), float("nan"))
    u_wind = _mean(imdaa.get("u_wind"), float("nan"))
    v_wind = _mean(imdaa.get("v_wind"), float("nan"))
    wind_speed = float(np.hypot(u_wind, v_wind))

    observed_time = insat["observed_at"]
    if imdaa and "observed_at" in imdaa:
        observed_time = max(observed_time, imdaa["observed_at"])

    return {
        "source": "MOSDAC/INSAT-3D + IMDAA",
        "observed_at": observed_time,
        "satellite_products": {"insat": str(insat_path), "imdaa": str(imdaa_path) if imdaa_path else "Not Available"},
        "rainfall_15m_rate": qpe,
        "rainfall_1h_accum": qpe,
        "rainfall_3h_accum": qpe * 3,
        "radar_reflectivity_dbz": float("nan"),
        "temperature_c": temperature,
        "humidity_percent": min(100.0, max(0.0, iwv * 1.7)),
        "wind_speed_kmh": wind_speed,
        "wind_gust_kmh": wind_speed * 1.5,
        "iwv": iwv,
        "iwv_change": float("nan"),
        "ctt": ctt,
        "ctt_drop_rate": float("nan"),
        "qpe_mm_hr": qpe,
        "cape_j_kg": float("nan"),
        "lifted_index": float("nan"),
        "cin_j_kg": float("nan"),
        "low_level_convergence": float("nan"),
        "wind_shear_ms": float("nan"),
    }


def configured_product_endpoints() -> dict[str, str]:
    """Expose configured portal endpoints for health checks and operator setup."""
    settings = get_settings()
    return {
        "mosdac": settings.mosdac_api_url,
        "imdaa": settings.imdaa_api_url,
        "refresh_minutes": str(settings.satellite_refresh_minutes),
    }
