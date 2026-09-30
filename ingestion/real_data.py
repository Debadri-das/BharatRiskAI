"""Adapters and derivations for real IMDAA, INSAT, and DEM files.

The adapters are intentionally file-based: download/authentication is environment-specific,
while decoding and scientific transforms remain deterministic and testable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import re

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
    if fallback is not None:
        return fallback
    raise ValueError("Dataset has no timestamp coordinate (time, valid_time, or observation_time)")


def discover_tier1_files(root: str | Path) -> dict[str, list[Path]]:
    """Discover Tier-1 products deterministically, without downloading or fabricating data.

    INSAT products are classified from their directory/name (WV, TIR/IR, QPE/HEM),
    while IMDAA and terrain are classified by their on-disk format.  Results are
    sorted by path so repeated runs do not depend on filesystem ordering.
    """
    root = Path(root)
    insat: dict[str, list[Path]] = {"wv": [], "tir": [], "qpe": []}
    for path in sorted((root / "data" / "insat").rglob("*")) if (root / "data" / "insat").exists() else []:
        if not path.is_file() or path.suffix.lower() not in {".npz", ".nc", ".nc4", ".netcdf", ".h5", ".hdf5"}:
            continue
        label = f"{path.parent.name}/{path.stem}".lower()
        if re.search(r"(^|[._/-])(qpe|hem)([._/-]|$)", label):
            insat["qpe"].append(path)
        elif re.search(r"(^|[._/-])(tir|ir|thermal)([._/-]|$)", label):
            insat["tir"].append(path)
        elif re.search(r"(^|[._/-])(wv|water.?vapor)([._/-]|$)", label):
            insat["wv"].append(path)
        elif path.suffix.lower() == ".npz":
            # Extracted L1C files often carry a timestamp-only filename. Inspect
            # array names (not values) to identify their products deterministically.
            try:
                with np.load(path, allow_pickle=False) as data:
                    keys = set(data.files)
                if "wv_radiance" in keys:
                    insat["wv"].append(path)
                if "tir1_bt_k" in keys:
                    insat["tir"].append(path)
                if "qpe" in keys or "qpe_rate_mm_hr" in keys:
                    insat["qpe"].append(path)
            except (OSError, ValueError):
                # Discovery remains non-validating; validation reports malformed files.
                pass
    imdaa = sorted(p for p in (root / "data" / "imdaa").rglob("*") if p.is_file() and p.suffix.lower() in {".nc", ".nc4", ".netcdf"}) if (root / "data" / "imdaa").exists() else []
    terrain = sorted(p for base in ("dem", "terrain", "elevation") for p in ((root / "data" / base).rglob("*") if (root / "data" / base).exists() else []) if p.is_file() and p.suffix.lower() in {".tif", ".tiff"})
    return {**insat, "imdaa": imdaa, "terrain": sorted(set(terrain))}


def _validate_geo(latitude: np.ndarray, longitude: np.ndarray) -> None:
    if latitude.size == 0 or longitude.size == 0:
        raise ValueError("Product latitude/longitude arrays must be non-empty")
    if latitude.ndim not in (1, 2) or longitude.ndim not in (1, 2):
        raise ValueError("Product latitude/longitude must be one- or two-dimensional")
    if latitude.ndim == 2 and longitude.ndim == 2 and latitude.shape != longitude.shape:
        raise ValueError("Two-dimensional latitude/longitude arrays must have the same shape")
    if not (np.all(np.isfinite(latitude)) and np.all(np.isfinite(longitude))):
        raise ValueError("Product latitude/longitude contains non-finite values")
    if np.any(np.abs(latitude) > 90) or np.any(np.abs(longitude) > 180):
        raise ValueError("Product latitude/longitude is outside geographic bounds")


def validate_insat_npz(path: str | Path, product: str) -> dict[str, Any]:
    """Validate an extracted INSAT WV/TIR/QPE NPZ contract and return its metadata."""
    required = {"wv": {"wv_radiance"}, "tir": {"tir1_bt_k"}, "qpe": {"qpe"}}[product]
    with np.load(path, allow_pickle=False) as data:
        available = set(data.files)
        product_required = set(required)
        if product == "qpe" and "qpe_rate_mm_hr" in available:
            product_required.discard("qpe")
        missing = (product_required | {"timestamp", "latitude", "longitude"}) - available
        if missing:
            raise ValueError(f"INSAT {product} file missing required arrays: {sorted(missing)}")
        timestamp = str(data["timestamp"])
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"INSAT timestamp is not ISO-8601: {timestamp!r}") from exc
        lat, lon = np.asarray(data["latitude"]), np.asarray(data["longitude"])
        _validate_geo(lat, lon)
        value_name = next(iter(required))
        if value_name == "qpe" and value_name not in data and "qpe_rate_mm_hr" in data:
            value_name = "qpe_rate_mm_hr"
        values = np.asarray(data[value_name])
        if values.size == 0 or not np.issubdtype(values.dtype, np.number):
            raise ValueError(f"INSAT {product} values must be a non-empty numeric array")
        return {"product": product, "timestamp": timestamp, "shape": values.shape, "path": str(path)}


def validate_imdaa_file(path: str | Path) -> dict[str, Any]:
    """Validate required IMDAA profile variables, coordinates, timestamps, and units."""
    dataset = _require_xarray().open_dataset(path)
    try:
        names = {**DEFAULT_IMDAA_VARIABLES}
        for key, name in names.items():
            if name not in dataset:
                raise ValueError(f"IMDAA file missing required variable {name!r}")
            if not str(dataset[name].attrs.get("units", "")).strip():
                raise ValueError(f"IMDAA variable {name!r} has no units")
        lat_name = "lat" if "lat" in dataset else "latitude" if "latitude" in dataset else None
        lon_name = "lon" if "lon" in dataset else "longitude" if "longitude" in dataset else None
        if lat_name is None or lon_name is None:
            raise ValueError("IMDAA file has no latitude/longitude coordinates")
        _validate_geo(np.asarray(dataset[lat_name].values), np.asarray(dataset[lon_name].values))
        timestamp = _timestamp(dataset).isoformat()
        if np.asarray(dataset[names["pressure"]]).ndim != 1:
            raise ValueError("IMDAA pressure coordinate must be one-dimensional")
        return {"timestamp": timestamp, "variables": names, "path": str(path)}
    finally:
        dataset.close()


def validate_dem_file(path: str | Path) -> dict[str, Any]:
    """Validate a SRTM/NASADEM GeoTIFF as a georeferenced elevation raster."""
    if rasterio is None:
        raise RuntimeError("rasterio is required for DEM ingestion")
    with rasterio.open(path) as dataset:
        if dataset.count < 1 or dataset.width < 1 or dataset.height < 1 or dataset.crs is None:
            raise ValueError("DEM must have a non-empty band and CRS")
        units = dataset.tags(1).get("units") or dataset.tags().get("units") or dataset.tags().get("UNITTYPE")
        if units and str(units).lower() not in {"m", "meter", "meters", "metre", "metres"}:
            raise ValueError(f"DEM elevation units must be metres, got {units!r}")
        values = dataset.read(1, masked=True)
        if values.count() == 0 or not np.any(np.isfinite(values.compressed())):
            raise ValueError("DEM contains no finite elevation values")
        return {"path": str(path), "crs": str(dataset.crs), "units": units or "metres (GeoTIFF elevation convention)"}


def validate_tier1_sources(root: str | Path) -> dict[str, Any]:
    """Validate every discovered Tier-1 source; missing sources are reported, never filled."""
    files = discover_tier1_files(root)
    result: dict[str, Any] = {"files": files, "valid": {}, "errors": {}}
    for product in ("wv", "tir", "qpe"):
        if not files[product]:
            result["errors"][f"insat_{product}"] = "no files discovered"
        else:
            try:
                result["valid"][f"insat_{product}"] = validate_insat_npz(files[product][-1], product) if files[product][-1].suffix.lower() == ".npz" else {"path": str(files[product][-1]), "format": files[product][-1].suffix.lower()}
            except (OSError, ValueError, KeyError) as exc:
                result["errors"][f"insat_{product}"] = str(exc)
    if files["imdaa"]:
        try: result["valid"]["imdaa"] = validate_imdaa_file(files["imdaa"][-1])
        except (OSError, ValueError, KeyError) as exc: result["errors"]["imdaa"] = str(exc)
    else: result["errors"]["imdaa"] = "no files discovered"
    if files["terrain"]:
        try: result["valid"]["terrain"] = validate_dem_file(files["terrain"][-1])
        except (OSError, ValueError, KeyError) as exc: result["errors"]["terrain"] = str(exc)
    else: result["errors"]["terrain"] = "no files discovered"
    return result


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
    validate_imdaa_file(path)
    dataset = _require_xarray().open_dataset(path)
    try:
        names = {**DEFAULT_IMDAA_VARIABLES, **(variables or {})}
        pressure_name = names["pressure"]
        lat_name = "lat" if "lat" in dataset else "latitude"
        lon_name = "lon" if "lon" in dataset else "longitude"
        def profile(name: str) -> np.ndarray:
            value = dataset[name]
            if "time" in value.dims:
                if value.sizes["time"] != 1:
                    raise ValueError("One IMDAA file must contain exactly one timestamp")
                value = value.isel(time=0)
            return np.asarray(value.transpose(pressure_name, lat_name, lon_name).values, dtype=np.float64)
        q = profile(names["specific_humidity"])
        pressure = _array(dataset, pressure_name)
        result = {
            "source": "IMDAA", "observed_at": _timestamp(dataset).isoformat(),
            "iwv": integrated_water_vapor(q, pressure), "temperature": profile(names["temperature"]),
            "u_wind": profile(names["u_wind"]), "v_wind": profile(names["v_wind"]),
            "latitude": _array(dataset, lat_name), "longitude": _array(dataset, lon_name),
            "pressure_pa": pressure * 100.0 if np.nanmax(pressure) < 2000 else pressure,
            "specific_humidity": q, "metadata": {"path": str(path), "variables": names},
        }
        for rainfall_name in ("rainfall", "pr", "precipitation_rate"):
            if rainfall_name in dataset:
                value = dataset[rainfall_name]
                if "time" in value.dims:
                    value = value.isel(time=0)
                result["rainfall"] = np.asarray(value.transpose(lat_name, lon_name).values, dtype=np.float64)
                result["metadata"]["rainfall_variable"] = rainfall_name
                result["metadata"]["rainfall_units"] = dataset[rainfall_name].attrs.get("units")
                break
        return result
    finally:
        dataset.close()


def read_insat(path: str | Path, variables: dict[str, str] | None = None) -> dict[str, Any]:
    """Read standardized INSAT-3DR L1C products from the extraction pipeline."""
    with np.load(path, allow_pickle=False) as data:
        return {
            "source": "INSAT-3DR",
            "observed_at": str(data["timestamp"]),
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "wv_radiance": data["wv_radiance"],
            "tir1_bt_k": data["tir1_bt_k"],
            "tir2_bt_k": data["tir2_bt_k"],
            "vis_radiance": data["vis_radiance"],
            "vis_albedo_percent": data.get("vis_albedo_percent"),
            "metadata": {
                "path": str(path),
                "contract": "reports/insat_l1c_contract.md",
                "calibration": "Radiance uses lab_radiance_quad + scale_factor*count + add_offset; TIR uses provider temperature LUT; WV remains radiance, not IWV."
            }
        }


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
            "observed_at": None,
            "elevation": elevation,
            "slope": slope,
            "metadata": {"path": str(path), "crs": str(dataset.crs), "transform": list(dataset.transform)[:6]},
        }


def latest_file(directory: str | Path, suffixes: Iterable[str]) -> Path | None:
    candidates = [item for item in Path(directory).glob("*") if item.is_file() and item.suffix.lower() in {s.lower() for s in suffixes}]
    return max(candidates, key=lambda item: item.stat().st_mtime, default=None)
