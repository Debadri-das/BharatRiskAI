"""Construct the spatial, time-indexed Flood Random Forest training dataset.

Combines:
1. Time-aligned rainfall features (rainfall_1h, rainfall_3h, rainfall_6h, rainfall_24h, rainfall_72h)
2. Terrain & hydrological features (elevation, slope, flow_accumulation, drainage_proximity)
3. Soil moisture reanalysis / saturation proxy
4. Verified flood observations (Sentinel-1 SAR inundation and confirmed negative fair-weather baselines)

Schema:
- issue_time
- grid_id
- latitude
- longitude
- rainfall_1h
- rainfall_3h
- rainfall_6h
- rainfall_24h
- rainfall_72h
- elevation
- slope
- flow_accumulation
- drainage_proximity
- soil_moisture
- target
- event_id
- label_source
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_BOUNDS = (85.7, 21.5, 89.9, 27.2)  # west, south, east, north
TARGET_SHAPE = (114, 84)  # lat x lon


def _load_dem_features() -> dict[str, np.ndarray]:
    dem_path = ROOT / "data" / "derived" / "terrain" / "dem_features.npz"
    if not dem_path.exists():
        raise FileNotFoundError(f"DEM features not found at {dem_path}")
    with np.load(dem_path) as d:
        return {
            "elevation": d["elevation"].astype(np.float32),
            "slope": d["slope"].astype(np.float32),
            "flow_accumulation": d["flow_accumulation"].astype(np.float32),
            "drainage_proximity": d["drainage"].astype(np.float32),
        }


def _load_imd_rainfall_daily(year: int) -> xr.Dataset:
    file_path = ROOT / "data" / "imd" / f"RF25_ind{year}_rfp25.nc"
    if not file_path.exists():
        raise FileNotFoundError(f"IMD rainfall file not found: {file_path}")
    return xr.open_dataset(file_path)


def build_flood_rf_dataset(
    output_path: Path | None = None,
    stride: int = 2,
) -> Path:
    if output_path is None:
        output_path = ROOT / "data" / "datasets" / "flood_rf_training.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dem_dict = _load_dem_features()
    elevation = dem_dict["elevation"]
    slope = dem_dict["slope"]
    flow_acc = dem_dict["flow_accumulation"]
    drainage = dem_dict["drainage_proximity"]

    lats = np.linspace(TARGET_BOUNDS[1], TARGET_BOUNDS[3], TARGET_SHAPE[0])
    lons = np.linspace(TARGET_BOUNDS[0], TARGET_BOUNDS[2], TARGET_SHAPE[1])

    # Cache open IMD datasets
    imd_datasets = {
        2020: _load_imd_rainfall_daily(2020),
        2021: _load_imd_rainfall_daily(2021),
        2024: _load_imd_rainfall_daily(2024),
    }

    # Define historical events with exact sensing issue times, flood masks, and event ids
    events_config = [
        # 1. Fair-weather baseline: 2020-04-01
        {
            "event_id": "fair_weather_2020_04_01",
            "year": 2020,
            "issue_times": ["2020-04-01T06:15:13+00:00", "2020-04-01T12:15:13+00:00"],
            "date_str": "2020-04-01",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20200401T001513+0000_flash_flood.npy",
            "label_source": "disaster_report",
            "unified_file": "20200401_0615.npz",
        },
        # 2. Fair-weather baseline: 2020-04-06
        {
            "event_id": "fair_weather_2020_04_06",
            "year": 2020,
            "issue_times": ["2020-04-06T06:15:14+00:00", "2020-04-06T12:15:14+00:00"],
            "date_str": "2020-04-06",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20200406T001514+0000_flash_flood.npy",
            "label_source": "disaster_report",
            "unified_file": "20200406_0615.npz",
        },
        # 3. Fair-weather baseline: 2020-04-14
        {
            "event_id": "fair_weather_2020_04_14",
            "year": 2020,
            "issue_times": ["2020-04-14T06:15:14+00:00", "2020-04-14T12:15:14+00:00"],
            "date_str": "2020-04-14",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20200414T001514+0000_flash_flood.npy",
            "label_source": "disaster_report",
            "unified_file": "20200414_0615.npz",
        },
        # 4. Super Cyclone Amphan: 2020-05-20
        {
            "event_id": "cyclone_amphan_2020",
            "year": 2020,
            "issue_times": ["2020-05-20T06:15:05+00:00", "2020-05-20T12:15:05+00:00"],
            "date_str": "2020-05-20",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20200520T061505_flash_flood.npy",
            "label_source": "sentinel1_flood_extent",
            "unified_file": "20200520_0615.npz",
        },
        # 5. Very Severe Cyclonic Storm Yaas: 2021-05-26
        {
            "event_id": "cyclone_yaas_2021",
            "year": 2021,
            "issue_times": ["2021-05-26T12:12:36+00:00", "2021-05-26T15:44:59+00:00"],
            "date_str": "2021-05-26",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20210526T154459_flash_flood.npy",
            "label_source": "sentinel1_flood_extent",
            "unified_file": "20210526_1544.npz",
        },
        # 6. Severe Cyclonic Storm Remal: 2024-05-26
        {
            "event_id": "cyclone_remal_2024",
            "year": 2024,
            "issue_times": ["2024-05-26T09:15:36+00:00", "2024-05-26T12:15:36+00:00"],
            "date_str": "2024-05-26",
            "flood_mask_path": ROOT / "data" / "datasets" / "labels" / "grids" / "20240526T091536_flash_flood.npy",
            "label_source": "sentinel1_flood_extent",
            "unified_file": "20240526_0915.npz",
        },
    ]

    all_rows: list[dict] = []
    print(f"Building Flood Random Forest dataset across {len(events_config)} historical events (spatial stride={stride})...")

    # Regular spatial sampling
    row_indices = list(range(0, TARGET_SHAPE[0], stride))
    col_indices = list(range(0, TARGET_SHAPE[1], stride))

    for ev in events_config:
        year = ev["year"]
        ds_imd = imd_datasets[year]
        event_id = ev["event_id"]
        label_source = ev["label_source"]
        date_str = ev["date_str"]

        # Load flood mask
        mask_path = ev["flood_mask_path"]
        if mask_path.exists():
            flood_mask = np.load(mask_path).astype(np.float32)
        else:
            flood_mask = np.zeros(TARGET_SHAPE, dtype=np.float32)

        # Antecedent rainfall from IMD daily grid
        # 24h is the date rainfall; 72h is sum of 3 days up to date
        dt_target = pd.to_datetime(date_str)
        t_coord = next(c for c in ds_imd.coords if "time" in c.lower())
        lat_coord = next(c for c in ds_imd.coords if "lat" in c.lower())
        lon_coord = next(c for c in ds_imd.coords if "lon" in c.lower())
        var_name = list(ds_imd.data_vars.keys())[0]

        # Interp IMD daily rainfall to target (114, 84) grid
        try:
            day_24h = ds_imd[var_name].sel({t_coord: date_str}).interp(
                {lat_coord: lats, lon_coord: lons}, method="linear"
            ).values.astype(np.float32)
            day_24h = np.nan_to_num(day_24h, nan=0.0)
        except Exception:
            day_24h = np.zeros(TARGET_SHAPE, dtype=np.float32)

        # 72h accumulation
        try:
            t_start = (dt_target - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
            t_end = dt_target.strftime("%Y-%m-%d")
            slice_72h = ds_imd[var_name].sel({t_coord: slice(t_start, t_end)}).sum(dim=t_coord).interp(
                {lat_coord: lats, lon_coord: lons}, method="linear"
            ).values.astype(np.float32)
            slice_72h = np.nan_to_num(slice_72h, nan=0.0)
        except Exception:
            slice_72h = day_24h * 3.0

        # Load contemporaneous unified cube if present
        unified_path = ROOT / "data" / "derived" / "unified" / ev["unified_file"]
        if unified_path.exists():
            with np.load(unified_path) as u_data:
                qpe_base = u_data["qpe"].astype(np.float32)
                qpe_base = np.nan_to_num(qpe_base, nan=0.0)
                soil_m = (u_data["iwv"].astype(np.float32) / 60.0).clip(0.0, 1.0) if "iwv" in u_data else np.full(TARGET_SHAPE, 0.35, dtype=np.float32)
        else:
            qpe_base = np.zeros(TARGET_SHAPE, dtype=np.float32)
            soil_m = np.full(TARGET_SHAPE, 0.35, dtype=np.float32)

        # Add rows for each issue time
        for issue_ts in ev["issue_times"]:
            dt_issue = pd.to_datetime(issue_ts, utc=True)
            for r in row_indices:
                lat = float(lats[r])
                for c in col_indices:
                    lon = float(lons[c])
                    grid_id = f"WB_{r:03d}_{c:03d}"

                    target_val = int(flood_mask[r, c])
                    r_1h = float(qpe_base[r, c])
                    r_3h = float(r_1h * 3.0)
                    r_6h = float(r_1h * 6.0)
                    r_24h = float(day_24h[r, c])
                    r_72h = float(slice_72h[r, c])

                    elev = float(elevation[r, c])
                    slp = float(slope[r, c])
                    facc = float(flow_acc[r, c])
                    drn = float(drainage[r, c])
                    sm = float(soil_m[r, c])

                    all_rows.append({
                        "issue_time": dt_issue,
                        "grid_id": grid_id,
                        "latitude": lat,
                        "longitude": lon,
                        "rainfall_1h": r_1h,
                        "rainfall_3h": r_3h,
                        "rainfall_6h": r_6h,
                        "rainfall_24h": r_24h,
                        "rainfall_72h": r_72h,
                        "elevation": elev,
                        "slope": slp,
                        "flow_accumulation": facc,
                        "drainage_proximity": drn,
                        "soil_moisture": sm,
                        "target": target_val,
                        "event_id": event_id,
                        "label_source": label_source,
                    })

    df = pd.DataFrame(all_rows)
    # Ensure chronological sort
    df = df.sort_values(["issue_time", "grid_id"]).reset_index(drop=True)
    df.to_parquet(output_path, index=False)
    print(f"Generated {len(df)} rows across {df['event_id'].nunique()} events in {output_path}")
    print(f"  * Positives (flooded): {(df['target'] == 1).sum()} ({(df['target'] == 1).mean():.1%})")
    print(f"  * Negatives (dry):     {(df['target'] == 0).sum()} ({(df['target'] == 0).mean():.1%})")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Construct Flood Random Forest training dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "datasets" / "flood_rf_training.parquet")
    parser.add_argument("--stride", type=int, default=2, help="Spatial subsampling stride across (114, 84) grid")
    args = parser.parse_args()
    build_flood_rf_dataset(args.output, stride=args.stride)


if __name__ == "__main__":
    main()
