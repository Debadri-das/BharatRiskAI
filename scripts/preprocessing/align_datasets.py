"""Write the common-grid contract, harmonize ERA5/IMDAA atmospheric fields, and verify feature shapes."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union

import numpy as np
import xarray as xr

# Robust project root resolution (checks for the 'data' directory)
CURRENT_FILE = Path(__file__).resolve()
ROOT = (
    CURRENT_FILE.parents[1]
    if (CURRENT_FILE.parents[1] / "data").exists()
    else CURRENT_FILE.parents[2]
)

GRID = {
    "crs": "EPSG:4326",
    "resolution_degrees": [0.05, 0.05],
    "extent": {"west": 85.7, "south": 21.5, "east": 89.9, "north": 27.2},
    "shape": [114, 84],
    "temporal_interval_minutes": 30,
}


def harmonize_era5(
    era5_source: Union[str, Path, xr.Dataset],
    target_grid: Optional[dict] = None,
    imdaa_template_path: Optional[Union[str, Path]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """Harmonize ERA5 pressure-level NetCDF to match IMDAA variables, units, and spatial grid.

    - Renames single-letter CDS variables (t, u, v, r/q) to IMDAA-compatible names.
    - Converts Geopotential (z in m^2/s^2) to Geopotential Height (m) via g0 = 9.80665.
    - Interpolates grid to match target coordinates (GRID or template).
    """
    if isinstance(era5_source, (str, Path)):
        ds = xr.open_dataset(era5_source)
    else:
        ds = era5_source.copy()

    # 1. Normalize coordinate dimension names
    coord_rename = {}
    if "latitude" not in ds.coords and "lat" in ds.coords:
        coord_rename["lat"] = "latitude"
    if "longitude" not in ds.coords and "lon" in ds.coords:
        coord_rename["lon"] = "longitude"
    if "valid_time" in ds.coords and "time" not in ds.coords:
        coord_rename["valid_time"] = "time"
    if coord_rename:
        ds = ds.rename(coord_rename)

    # 2. Standardize variable names to match IMDAA convention
    var_mapping = {
        "t": "temperature",
        "u": "u_wind",
        "v": "v_wind",
        "r": "relative_humidity",
        "q": "specific_humidity",
    }
    rename_vars = {k: v for k, v in var_mapping.items() if k in ds.data_vars}
    ds = ds.rename(rename_vars)

    # 3. Convert Geopotential (z) to Geopotential Height
    if "z" in ds.data_vars:
        ds["geopotential_height"] = ds["z"] / 9.80665
        ds["geopotential_height"].attrs["units"] = "m"
        ds["geopotential_height"].attrs["long_name"] = "Geopotential height"
        ds = ds.drop_vars("z")

    # 4. Determine target latitudes and longitudes
    if imdaa_template_path is not None:
        template = xr.open_dataset(imdaa_template_path)
        target_lats = template["latitude"] if "latitude" in template else template["lat"]
        target_lons = template["longitude"] if "longitude" in template else template["lon"]
    else:
        # Default to canonical common GRID contract
        cfg = target_grid or GRID
        ext = cfg["extent"]
        target_lats = np.linspace(ext["south"], ext["north"], cfg["shape"][0])
        target_lons = np.linspace(ext["west"], ext["east"], cfg["shape"][1])

    # 5. Bilinear regridding to target grid
    ds_harmonized = ds.interp(
        latitude=target_lats,
        longitude=target_lons,
        method="linear",
    )

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        ds_harmonized.to_netcdf(out_p)

    return ds_harmonized


def jitter_and_gaps(timestamps: list[str]) -> tuple[list[dict], list[dict]]:
    """Separate provider clock jitter from real temporal gaps."""
    parsed = sorted(datetime.fromisoformat(value.replace("Z", "+00:00")) for value in timestamps)
    if not parsed:
        return [], []
    if any((stamp.tzinfo is None) != (parsed[0].tzinfo is None) for stamp in parsed):
        raise ValueError("timestamps must consistently include or omit timezone information")

    jitter: list[dict] = []
    for stamp in parsed:
        nominal = stamp.replace(minute=(15 if stamp.minute < 30 else 45), second=0, microsecond=0)
        offset = (stamp - nominal).total_seconds()
        if abs(offset) > 0:
            jitter.append({"timestamp": stamp.isoformat(), "offset_seconds_from_nominal_slot": offset})

    gaps: list[dict] = []
    for previous, current in zip(parsed, parsed[1:]):
        delta = current - previous
        if delta > timedelta(minutes=GRID["temporal_interval_minutes"] * 1.25):
            gaps.append({
                "from": previous.isoformat(),
                "to": current.isoformat(),
                "minutes": delta.total_seconds() / 60.0,
                "missing_slots": int(delta // timedelta(minutes=GRID["temporal_interval_minutes"])) - 1,
            })
    return jitter, gaps


def main() -> None:
    # 1. Check and harmonize any staged ERA5 file in data/imdaa/
    imdaa_dir = ROOT / "data" / "imdaa"
    era5_mapping = {
        "data_stream": "yaas_era5_harmonized.nc",
        "48ede98f": "remal_era5_harmonized.nc",
    }
    for file_path in imdaa_dir.glob("*.nc"):
        for key, target_name in era5_mapping.items():
            if key in file_path.name:
                target_harmonized_path = imdaa_dir / target_name
                if not target_harmonized_path.exists():
                    print(f"Harmonizing staged atmospheric file: {file_path.name} -> {target_name}...")
                    harmonize_era5(file_path, output_path=target_harmonized_path)
                    print(f"Saved harmonized dataset to: {target_name}")

    # 2. Audit derived satellite features
    feature_dir = ROOT / "data" / "derived" / "satellite"
    files = sorted(feature_dir.glob("*.npz"))
    mismatches = []
    timestamps = []

    for path in files:
        with np.load(path, allow_pickle=False) as data:
            timestamps.append(str(data["timestamp"]))
            shapes = {name: list(data[name].shape) for name in data.files if name != "timestamp"}
            if any(shape != GRID["shape"] for shape in shapes.values()):
                mismatches.append({"path": str(path.relative_to(ROOT)), "shapes": shapes})

    jitter, gaps = jitter_and_gaps(timestamps)
    output = ROOT / "data" / "derived" / "grid_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "grid": GRID,
                "file_count": len(files),
                "timestamps": timestamps,
                "shape_mismatches": mismatches,
                "provider_timestamp_jitter": jitter,
                "temporal_gaps": gaps,
                "qpe_temporal_note": "The available QPE sample is 2024-06-18 and does not overlap the 2023-07-01 L1C sequence; it is not joined as a contemporaneous feature.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if mismatches:
        raise RuntimeError(f"Common-grid validation failed for {len(mismatches)} files")
    print(f"Manifest written to: {output}")


if __name__ == "__main__":
    main()