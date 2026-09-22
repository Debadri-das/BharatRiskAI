"""Adapters and derivations for real IMDAA, INSAT, and DEM files.

The adapters are intentionally file-based: download/authentication is environment-specific,
while decoding and scientific transforms remain deterministic and testable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:
    import xarray as xr
except ImportError:  # pragma: no cover
    xr = None

try:
    import rasterio
except ImportError:  # pragma: no cover
    rasterio = None


DEFAULT_IMDAA_VARIABLES = {
    "temperature": "ta",
    "specific_humidity": "hus",
    "pressure": "plev",
    "u_wind": "ua",
    "v_wind": "va",
}
DEFAULT_INSAT_VARIABLES = {
    "water_vapor": "water_vapor",
    "thermal_ir": "thermal_ir",
    "qpe": "qpe",
}


def _require_xarray() -> Any:
    if xr is None:
        raise RuntimeError("xarray is required for NetCDF/HDF5 ingestion")
    return xr


def _array(dataset: Any, name: str) -> np.ndarray:
    if name not in dataset:
        raise KeyError(f"Required variable '{name}' is missing from the dataset")
    return np.asarray(dataset[name].values, dtype=np.float64)


def _timestamp(dataset: Any, fallback: datetime | None = None) -> datetime:
    for name in ("time", "valid_time", "observation_time"):
        if name in dataset.coords and dataset[name].size:
            value = dataset[name].values.reshape(-1)[0]
            if hasattr(value, "item"):
                value = value.item()
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    return fallback or datetime.now(timezone.utc)


def integrated_water_vapor(specific_humidity: np.ndarray, pressure_pa: np.ndarray) -> np.ndarray:
    """Calculate IWV in kg/m2 by integrating q dp/g through pressure levels."""
    q = np.asarray(specific_humidity, dtype=np.float64)
    pressure = np.asarray(pressure_pa, dtype=np.float64)
    if q.shape != pressure.shape and pressure.ndim != 1:
        raise ValueError("specific humidity and pressure must share shape or pressure must be 1-D")
    if pressure.ndim == 1:
        pressure = pressure.reshape((-1,) + (1,) * (q.ndim - 1))
    if np.nanmax(pressure) < 2000:
        pressure = pressure * 100.0
    order = np.argsort(pressure[:, 0, 0] if pressure.ndim > 1 else pressure)
    q = np.take(q, order, axis=0)
    pressure = np.take(pressure, order, axis=0)
    integrate = getattr(np, "trapezoid", np.trapz)
    return integrate(q, pressure, axis=0) / 9.80665


def cloud_top_temperature(thermal_ir: np.ndarray, scale: float = 1.0, offset: float = 0.0, kelvin: bool = True) -> np.ndarray:
    """Convert calibrated TIR brightness temperature to Celsius."""
    values = np.asarray(thermal_ir, dtype=np.float64) * scale + offset
    return values - 273.15 if kelvin and np.nanmean(values) > 100 else values


def temporal_change(current: np.ndarray, previous: np.ndarray | None, hours: float) -> np.ndarray:
    if previous is None:
        return np.zeros_like(current, dtype=np.float64)
    if hours <= 0:
        raise ValueError("hours must be positive")
    return (current - previous) / hours


def read_imdaa(path: str | Path, variables: dict[str, str] | None = None) -> dict[str, Any]:
    dataset = _require_xarray().open_dataset(path)
    names = {**DEFAULT_IMDAA_VARIABLES, **(variables or {})}
    q = _array(dataset, names["specific_humidity"])
    pressure = _array(dataset, names["pressure"])
    iwv = integrated_water_vapor(q, pressure)
    return {
        "source": "IMDAA",
        "observed_at": _timestamp(dataset).isoformat(),
        "iwv": iwv,
        "temperature": _array(dataset, names["temperature"]),
        "u_wind": _array(dataset, names["u_wind"]),
        "v_wind": _array(dataset, names["v_wind"]),
        "metadata": {"path": str(path), "variables": names},
    }


def read_insat(path: str | Path, variables: dict[str, str] | None = None, tir_scale: float = 1.0, tir_offset: float = 0.0) -> dict[str, Any]:
    dataset = _require_xarray().open_dataset(path, engine="h5netcdf" if str(path).lower().endswith((".h5", ".hdf5")) else None)
    names = {**DEFAULT_INSAT_VARIABLES, **(variables or {})}
    result = {"source": "INSAT-3D/3DR", "observed_at": _timestamp(dataset).isoformat(), "metadata": {"path": str(path), "variables": names}}
    result["iwv"] = _array(dataset, names["water_vapor"])
    result["ctt"] = cloud_top_temperature(_array(dataset, names["thermal_ir"]), tir_scale, tir_offset)
    if names["qpe"] in dataset:
        result["qpe"] = _array(dataset, names["qpe"])
    return result


def read_dem(path: str | Path) -> dict[str, Any]:
    if rasterio is None:
        raise RuntimeError("rasterio is required for DEM ingestion")
    with rasterio.open(path) as dataset:
        elevation = dataset.read(1).astype(np.float64)
        x_resolution, y_resolution = abs(dataset.transform.a), abs(dataset.transform.e)
        gy, gx = np.gradient(elevation, y_resolution, x_resolution)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        return {
            "source": "DEM",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "elevation": elevation,
            "slope": slope,
            "metadata": {"path": str(path), "crs": str(dataset.crs), "transform": list(dataset.transform)[:6]},
        }


def latest_file(directory: str | Path, suffixes: Iterable[str]) -> Path | None:
    candidates = [item for item in Path(directory).glob("*") if item.is_file() and item.suffix.lower() in {s.lower() for s in suffixes}]
    return max(candidates, key=lambda item: item.stat().st_mtime, default=None)
