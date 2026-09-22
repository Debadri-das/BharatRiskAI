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
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject
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
    "water_vapor": "IMG_WV",
    "thermal_ir": "IMG_TIR1",
    "qpe": "HEM",
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
            if isinstance(value, np.datetime64):
                value = value.astype("datetime64[us]").astype(datetime)
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


def _geo(dataset: Any, name: str, scale: float = 1.0) -> np.ndarray:
    values = _array(dataset, name)
    if np.nanmax(np.abs(values)) > 180:
        values = values * scale
    return values


def _lut_temperature(counts: np.ndarray, lut: np.ndarray) -> np.ndarray:
    result = np.full(counts.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(counts) & (counts >= 0) & (counts < len(lut)) & (counts != 1023)
    result[valid] = np.asarray(lut)[counts[valid].astype(np.int64)]
    return result


def target_grid(dem_path: str | Path) -> dict[str, Any]:
    if rasterio is None:
        raise RuntimeError("rasterio is required for grid alignment")
    with rasterio.open(dem_path) as dataset:
        return {"crs": dataset.crs, "transform": dataset.transform, "width": dataset.width, "height": dataset.height, "shape": (dataset.height, dataset.width)}


def align_to_grid(values: np.ndarray, latitude: np.ndarray, longitude: np.ndarray, grid: dict[str, Any], *, nearest: bool = False) -> np.ndarray:
    """Reproject a geolocated product onto the DEM grid."""
    if rasterio is None:
        raise RuntimeError("rasterio is required for grid alignment")
    source = np.asarray(values, dtype=np.float32)
    source_lat = np.asarray(latitude, dtype=np.float64)
    source_lon = np.asarray(longitude, dtype=np.float64)
    valid = np.isfinite(source_lat) & np.isfinite(source_lon) & (np.abs(source_lat) <= 90) & (np.abs(source_lon) <= 180)
    if not np.any(valid):
        raise ValueError("Product has no valid geolocation")
    source_transform = from_bounds(float(np.nanmin(source_lon[valid])), float(np.nanmin(source_lat[valid])), float(np.nanmax(source_lon[valid])), float(np.nanmax(source_lat[valid])), source.shape[1], source.shape[0])
    destination = np.full(grid["shape"], np.nan, dtype=np.float32)
    reproject(source, destination, src_transform=source_transform, src_crs="EPSG:4326", dst_transform=grid["transform"], dst_crs=grid["crs"], src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest if nearest else Resampling.bilinear)
    return destination


def wind_diagnostics(u_wind: np.ndarray, v_wind: np.ndarray, latitude: np.ndarray, longitude: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return horizontal convergence (1/s) and vertical shear magnitude (m/s)."""
    earth_radius = 6_371_000.0
    lat = np.asarray(latitude, dtype=np.float64)
    dx = np.gradient(np.asarray(longitude, dtype=np.float64), axis=-1) * np.pi / 180.0 * earth_radius * np.cos(np.deg2rad(lat))
    dy = np.gradient(lat, axis=-2) * np.pi / 180.0 * earth_radius
    dx = np.where(np.abs(dx) < 1.0, np.nan, dx)
    dy = np.where(np.abs(dy) < 1.0, np.nan, dy)
    du_dx = np.gradient(np.asarray(u_wind, dtype=np.float64), axis=-1) / dx
    dv_dy = np.gradient(np.asarray(v_wind, dtype=np.float64), axis=-2) / dy
    convergence = -(du_dx + dv_dy)
    shear = np.hypot(np.gradient(np.asarray(u_wind, dtype=np.float64), axis=-2), np.gradient(np.asarray(v_wind, dtype=np.float64), axis=-2))
    return convergence, shear


def cape_cin(temperature_k: np.ndarray, specific_humidity: np.ndarray, pressure_pa: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute parcel CAPE and CIN for each IMDAA vertical profile."""
    try:
        from metpy.calc import cape_cin as metpy_cape_cin, dewpoint_from_specific_humidity, parcel_profile
        from metpy.units import units
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("metpy is required to compute CAPE/CIN from IMDAA profiles") from error
    temperature = np.asarray(temperature_k, dtype=np.float64)
    humidity = np.asarray(specific_humidity, dtype=np.float64)
    pressure = np.asarray(pressure_pa, dtype=np.float64)
    if pressure.ndim != 1:
        raise ValueError("pressure_pa must be one-dimensional")
    cape = np.full(temperature.shape[1:], np.nan, dtype=np.float64)
    cin = np.full(temperature.shape[1:], np.nan, dtype=np.float64)
    for index in np.ndindex(cape.shape):
        profile_pressure = pressure * units.pascal
        profile_temperature = temperature[(slice(None),) + index] * units.kelvin
        profile_humidity = humidity[(slice(None),) + index] * units.dimensionless
        dewpoint = dewpoint_from_specific_humidity(profile_pressure, profile_temperature, profile_humidity)
        parcel = parcel_profile(profile_pressure, profile_temperature[0], dewpoint[0])
        cape_value, cin_value = metpy_cape_cin(profile_pressure, profile_temperature, dewpoint, parcel)
        cape[index] = cape_value.to("joule / kilogram").magnitude
        cin[index] = cin_value.to("joule / kilogram").magnitude
    return cape, cin


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
        "latitude": _array(dataset, "lat" if "lat" in dataset else "latitude"),
        "longitude": _array(dataset, "lon" if "lon" in dataset else "longitude"),
        "pressure_pa": pressure,
        "specific_humidity": q,
        "metadata": {"path": str(path), "variables": names},
    }


def read_insat(path: str | Path, variables: dict[str, str] | None = None, tir_scale: float = 1.0, tir_offset: float = 0.0) -> dict[str, Any]:
    dataset = _require_xarray().open_dataset(path, engine="h5netcdf" if str(path).lower().endswith((".h5", ".hdf5")) else None)
    names = {**DEFAULT_INSAT_VARIABLES, **(variables or {})}
    result = {"source": "INSAT-3D/3DR", "observed_at": _timestamp(dataset).isoformat(), "metadata": {"path": str(path), "variables": names}}
    result["latitude"] = _geo(dataset, "Latitude", 0.01)
    result["longitude"] = _geo(dataset, "Longitude", 0.01)
    result["ctt"] = _lut_temperature(_array(dataset, names["thermal_ir"])[0], _array(dataset, "IMG_TIR1_TEMP"))
    result["wv_bt"] = _lut_temperature(_array(dataset, names["water_vapor"])[0], _array(dataset, "IMG_WV_TEMP"))
    result["metadata"]["calibration"] = "INSAT lookup-table brightness temperature; WV is not IWV"
    if names["qpe"] in dataset:
        result["qpe"] = _array(dataset, names["qpe"])[0]
    return result


def read_qpe(path: str | Path) -> dict[str, Any]:
    dataset = _require_xarray().open_dataset(path, engine="h5netcdf" if str(path).lower().endswith((".h5", ".hdf5")) else None)
    return {
        "source": "INSAT-3D/3DR-QPE",
        "observed_at": _timestamp(dataset).isoformat(),
        "latitude": _geo(dataset, "Latitude", 0.01),
        "longitude": _geo(dataset, "Longitude", 0.01),
        "qpe": _array(dataset, "HEM")[0],
        "metadata": {"path": str(path), "units": "mm/hr"},
    }


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
