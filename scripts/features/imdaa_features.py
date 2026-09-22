"""Extract and derive IMDAA features only when real profile files are present."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingestion.real_data import cape_cin, integrated_water_vapor, wind_diagnostics

ROOT = Path(__file__).resolve().parents[2]
ALIASES = {
    "temperature": ("ta", "temperature", "air_temperature"),
    "specific_humidity": ("hus", "specific_humidity", "q"),
    "pressure": ("plev", "pressure", "level", "isobaricInhPa"),
    "u_wind": ("ua", "u", "u_wind", "eastward_wind"),
    "v_wind": ("va", "v", "v_wind", "northward_wind"),
    "geopotential_height": ("zg", "geopotential_height", "height"),
}


def _find(dataset: object, candidates: tuple[str, ...]) -> str | None:
    names = set(getattr(dataset, "variables", {}))
    return next((name for name in candidates if name in names), None)


def process(path: Path, output: Path) -> Path:
    import xarray as xr
    from ingestion.real_data import _timestamp
    with xr.open_dataset(path) as dataset:
        names = {key: _find(dataset, candidates) for key, candidates in ALIASES.items()}
        required = [key for key in ("temperature", "specific_humidity", "pressure", "u_wind", "v_wind") if names[key] is None]
        if required:
            raise ValueError(f"IMDAA file is missing required profile variables: {required}; available={list(dataset.variables)}")
        temperature = np.asarray(dataset[names["temperature"]].values, dtype=np.float64)
        humidity = np.asarray(dataset[names["specific_humidity"]].values, dtype=np.float64)
        pressure = np.asarray(dataset[names["pressure"]].values, dtype=np.float64)
        if np.nanmax(pressure) < 2000:
            pressure = pressure * 100.0
        latitude_name = _find(dataset, ("lat", "latitude"))
        longitude_name = _find(dataset, ("lon", "longitude"))
        if latitude_name is None or longitude_name is None:
            raise ValueError("IMDAA file has no latitude/longitude coordinates")
        iwv = integrated_water_vapor(humidity, pressure)
        cape, cin = cape_cin(temperature, humidity, pressure)
        u = np.asarray(dataset[names["u_wind"]].values, dtype=np.float64)
        v = np.asarray(dataset[names["v_wind"]].values, dtype=np.float64)
        u_surface, v_surface = u[0], v[0]
        convergence, shear = wind_diagnostics(u_surface, v_surface, np.asarray(dataset[latitude_name].values), np.asarray(dataset[longitude_name].values))
        result = {"timestamp": _timestamp(dataset).isoformat(), "iwv": iwv, "cape": cape, "cin": cin, "convergence": convergence, "wind_shear": shear, "latitude": np.asarray(dataset[latitude_name].values), "longitude": np.asarray(dataset[longitude_name].values)}
        output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(output, **result)
        output.with_suffix(".json").write_text(json.dumps({"source": str(path.relative_to(ROOT)), "variables": names, "provenance": "IWV integrated q dp/g; CAPE/CIN from MetPy parcel thermodynamics; convergence is -(du/dx+dv/dy) in geographic meters; shear is surface-to-first-level vector-gradient proxy."}, indent=2), encoding="utf-8")
        return output


def main() -> None:
    paths = sorted((ROOT / "data" / "imdaa").rglob("*.nc")) + sorted((ROOT / "data" / "imdaa").rglob("*.nc4"))
    if not paths:
        raise FileNotFoundError("No IMDAA NetCDF files found; CAPE/CIN, IMDAA IWV, and IMDAA wind diagnostics cannot be generated.")
    for index, path in enumerate(paths):
        process(path, ROOT / "data" / "derived" / "atmospheric" / f"imdaa_{index:05d}.npz")


if __name__ == "__main__":
    main()
