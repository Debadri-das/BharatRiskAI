"""Derive timestamped atmospheric features from supplied IMDAA products.

The command is metadata-first and never creates values for unavailable
pressure-level or surface observations.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import xarray as xr

from ml.atmosphere.features import (
    bulk_wind_shear_0_6km,
    surface_based_cape_cin,
    horizontal_convergence,
    integrated_water_vapour,
    specific_humidity_from_relative_humidity,
)

LOG = logging.getLogger(__name__)

REQUIRED = {
    "temperature": ("TMP-prl", "temperature", "ta", "air_temperature", "t"),
    "relative_humidity": ("RH-prl", "relative_humidity", "rh", "r"),
    "u_wind": ("UGRD-prl", "u_wind", "ua", "eastward_wind", "u"),
    "v_wind": ("VGRD-prl", "v_wind", "va", "northward_wind", "v"),
    "height": ("HGT-prl", "geopotential_height", "zg", "height", "gh", "z"),
}


def _timestamp(dataset: xr.Dataset) -> datetime:
    for name in ("valid_time", "time", "forecast_time"):
        if name in dataset.coords and dataset[name].size:
            value = dataset[name].values.reshape(-1)[0]
            if isinstance(value, np.datetime64):
                value = value.astype("datetime64[us]").astype(datetime)
            if not isinstance(value, datetime):
                value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raise ValueError("Dataset has no valid timestamp coordinate")


def _find(dataset: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    return next((name for name in candidates if name in dataset.variables), None)


def _units(dataset: xr.Dataset, name: str) -> str:
    units = str(dataset[name].attrs.get("units", "")).strip()
    if not units:
        defaults = {"t": "K", "r": "%", "u": "m s-1", "v": "m s-1", "gh": "m", "z": "m2 s-2"}
        return defaults.get(name, "unknown")
    return units


def derive_profile_dataset(pressure: xr.Dataset, single: xr.Dataset | None = None) -> xr.Dataset:
    names = {key: _find(pressure, candidates) for key, candidates in REQUIRED.items()}
    missing = [key for key, name in names.items() if name is None]
    if missing:
        raise ValueError(f"Pressure-level dataset is missing variables: {missing}")

    level_name = next(
        (name for name in ("isobaricInhPa", "pressure", "level", "plev", "pressure_level") if name in pressure.coords),
        None,
    )
    lat_name = next((name for name in ("latitude", "lat") if name in pressure.coords), None)
    lon_name = next((name for name in ("longitude", "lon") if name in pressure.coords), None)
    if not level_name or not lat_name or not lon_name:
        raise ValueError("Pressure-level dataset must expose pressure, latitude and longitude coordinates")

    # Crop to study region margin if dataset is regional to keep thermodynamic profiles fast
    lats = np.asarray(pressure[lat_name].values, dtype=float)
    lons = np.asarray(pressure[lon_name].values, dtype=float)
    lons_norm = np.where(lons > 180, lons - 360, lons)
    if lats.min() < 20.0 or lats.max() > 29.0 or lons_norm.min() < 84.0 or lons_norm.max() > 91.0:
        lat_mask = (lats >= 20.5) & (lats <= 28.5)
        lon_mask = (lons_norm >= 84.5) & (lons_norm <= 91.0)
        if lat_mask.any() and lon_mask.any():
            pressure = pressure.isel({lat_name: lat_mask, lon_name: lon_mask})

    level = np.asarray(pressure[level_name].values, dtype=float)
    level_pa = level * 100.0 if np.nanmedian(level) < 2_000 else level
    temperature = np.asarray(pressure[names["temperature"]].squeeze().values, dtype=float)
    rh = np.asarray(pressure[names["relative_humidity"]].squeeze().values, dtype=float)
    u = np.asarray(pressure[names["u_wind"]].squeeze().values, dtype=float)
    v = np.asarray(pressure[names["v_wind"]].squeeze().values, dtype=float)
    height = np.asarray(pressure[names["height"]].squeeze().values, dtype=float)

    # Convert geopotential (m2/s2) to height (m) if needed
    if np.nanmax(height) > 20_000 and np.nanmedian(height) > 50_000:
        height = height / 9.80665

    # Ensure levels are ordered ascending by pressure (bottom to top: 1000 -> 200 hPa)
    if level_pa[0] < level_pa[-1]:
        order = np.argsort(level_pa)[::-1]
        level_pa = level_pa[order]
        temperature = temperature[order]
        rh = rh[order]
        u = u[order]
        v = v[order]
        height = height[order]

    q = specific_humidity_from_relative_humidity(temperature, rh, level_pa[:, None, None])
    iwv = integrated_water_vapour(q, level_pa)
    cape, cin = surface_based_cape_cin(temperature, rh, level_pa)
    shear, shear_u, shear_v = bulk_wind_shear_0_6km(u, v, height)
    convergence = horizontal_convergence(
        u[0], v[0], np.asarray(pressure[lat_name].values), np.asarray(pressure[lon_name].values)
    )
    result = xr.Dataset(
        {
            "iwv": (("latitude", "longitude"), iwv.astype(np.float32), {"units": "kg m-2", "long_name": "integrated water vapour"}),
            "cape": (("latitude", "longitude"), cape.astype(np.float32), {"units": "J kg-1", "long_name": "surface-based convective available potential energy"}),
            "cin": (("latitude", "longitude"), cin.astype(np.float32), {"units": "J kg-1", "long_name": "surface-based convective inhibition"}),
            "wind_shear_0_6km": (("latitude", "longitude"), shear.astype(np.float32), {"units": "m s-1", "long_name": "0-6 km bulk wind shear"}),
            "wind_shear_u_0_6km": (("latitude", "longitude"), shear_u.astype(np.float32), {"units": "m s-1"}),
            "wind_shear_v_0_6km": (("latitude", "longitude"), shear_v.astype(np.float32), {"units": "m s-1"}),
            "horizontal_convergence": (("latitude", "longitude"), convergence.astype(np.float32), {"units": "s-1", "long_name": "horizontal wind convergence"}),
        },
        coords={"latitude": pressure[lat_name].values, "longitude": pressure[lon_name].values},
        attrs={
            "feature_schema_version": "atmospheric-v1",
            "source_valid_time": _timestamp(pressure).isoformat(),
            "iwv_method": "trapezoidal integral of RH-derived specific humidity dp/g",
            "cape_cin_method": "MetPy surface-based parcel profile; CIN retains the library sign convention",
            "wind_shear_method": "height-interpolated 0-6 km bulk vector shear",
            "convergence_method": "spherical latitude/longitude divergence",
        },
    )
    if single is not None:
        result.attrs["single_level_source_valid_time"] = _timestamp(single).isoformat()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pressure-dir", type=Path, default=ROOT / "data" / "imdaa")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed" / "atmospheric_features")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "atmospheric_feature_manifest.json"
    manifest: dict[str, Any] = {"schema_version": "atmospheric-v1", "records": []}

    # Find harmonized and multi-level files in data/imdaa
    candidates = sorted(args.pressure_dir.glob("*.nc*"))
    for path in candidates:
        try:
            with xr.open_dataset(path) as ds:
                # Check if file has all required profile variables
                names = {key: _find(ds, candidates) for key, candidates in REQUIRED.items()}
                if any(name is None for name in names.values()):
                    continue

                time_dim = next((c for c in ("valid_time", "time", "forecast_time") if c in ds.coords), None)
                if time_dim and ds[time_dim].size > 1:
                    # Multi-timestamp dataset
                    for t_idx in range(len(ds[time_dim])):
                        try:
                            sub = ds.isel({time_dim: t_idx})
                            ts = _timestamp(sub)
                            out_file = args.output_dir / f"atmospheric_{ts.strftime('%Y%m%dT%H%M%SZ')}.nc"
                            if out_file.exists() and not args.force:
                                manifest["records"].append({"source": f"{path.name} [t={t_idx}]", "timestamp": ts.isoformat(), "output": str(out_file), "status": "SKIPPED_EXISTING"})
                                continue
                            res = derive_profile_dataset(sub)
                            res.to_netcdf(out_file)
                            manifest["records"].append({"source": f"{path.name} [t={t_idx}]", "timestamp": ts.isoformat(), "output": str(out_file), "status": "ACCEPTED"})
                        except Exception as step_exc:
                            manifest["records"].append({"source": f"{path.name} [t={t_idx}]", "status": "BLOCKED", "reason": str(step_exc)})
                else:
                    ts = _timestamp(ds)
                    out_file = args.output_dir / f"atmospheric_{ts.strftime('%Y%m%dT%H%M%SZ')}.nc"
                    if out_file.exists() and not args.force:
                        manifest["records"].append({"source": path.name, "timestamp": ts.isoformat(), "output": str(out_file), "status": "SKIPPED_EXISTING"})
                        continue
                    res = derive_profile_dataset(ds)
                    res.to_netcdf(out_file)
                    manifest["records"].append({"source": path.name, "timestamp": ts.isoformat(), "output": str(out_file), "status": "ACCEPTED"})
        except Exception as exc:
            manifest["records"].append({"source": str(path), "status": "BLOCKED", "reason": str(exc)})

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    accepted = sum(1 for r in manifest["records"] if r.get("status") in ("ACCEPTED", "SKIPPED_EXISTING"))
    print(f"Processed atmospheric products: {accepted} accepted records")


if __name__ == "__main__":
    main()
