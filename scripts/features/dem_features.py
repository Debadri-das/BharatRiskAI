"""Derive terrain and hydrologically conditioned drainage features from Copernicus DEM.

Pipeline:
Copernicus DEM -> Sink filling / conditioning -> D8 Flow direction -> Flow accumulation -> Drainage score (0-100)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing.hydrology import compute_drainage_and_twi


def build(dem_path: Path, output: Path) -> Path:
    if not dem_path.exists():
        # Fallback to alternate DEM if configured path does not exist
        candidates = [
            ROOT / "data" / "dem" / "BharatRiskAI_WestBengal_DEM_GLO30.tif",
            ROOT / "data" / "dem" / "kolkata_dem.tif",
        ]
        found = next((c for c in candidates if c.exists()), None)
        if found is None:
            raise FileNotFoundError(f"Source DEM not found at {dem_path} or default locations.")
        dem_path = found

    with rasterio.open(dem_path) as source:
        elevation = np.full((114, 84), np.nan, dtype=np.float32)
        destination_transform = from_bounds(85.7, 21.5, 89.9, 27.2, 84, 114)
        reproject(
            source.read(1).astype(np.float32),
            elevation,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=destination_transform,
            dst_crs="EPSG:4326",
            src_nodata=source.nodata,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    # Calculate geographic gradient steps
    lat_step = np.deg2rad(0.05) * 6_371_000.0
    lon_step = np.deg2rad(0.05) * 6_371_000.0 * np.cos(np.deg2rad(24.35))
    gradient_y, gradient_x = np.gradient(elevation, lat_step, lon_step)
    slope = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y)))
    aspect = (np.degrees(np.arctan2(-gradient_x, gradient_y)) + 360.0) % 360.0
    gradient = np.hypot(gradient_x, gradient_y)

    # Hydrological preprocessing stage:
    # Sink filling / conditioning -> Flow direction -> Flow accumulation -> Drainage score
    filled_dem, flow_acc, drainage = compute_drainage_and_twi(
        elevation, slope, dy=float(lat_step), dx=float(lon_step)
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        elevation=elevation,
        filled_elevation=filled_dem.astype(np.float32),
        slope=slope.astype(np.float32),
        aspect=aspect.astype(np.float32),
        terrain_gradient=gradient.astype(np.float32),
        flow_accumulation=flow_acc.astype(np.float32),
        drainage=drainage.astype(np.float32),
    )
    
    metadata = {
        "source": str(dem_path.relative_to(ROOT)) if dem_path.is_relative_to(ROOT) else str(dem_path),
        "grid": {
            "crs": "EPSG:4326",
            "shape": [114, 84],
            "bounds": [85.7, 21.5, 89.9, 27.2],
            "resolution_degrees": [0.05, 0.05],
        },
        "drainage": {
            "status": "available",
            "method": "hydrologically conditioned D8 priority-flood sink filling, flow direction, flow accumulation and topographic wetness index (TWI)",
            "range": [0.0, 100.0],
            "units": "drainage score (0=waterlogged lowland/confluence, 100=well-drained ridge/upland)",
        },
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive terrain and hydrological drainage features from DEM")
    default_dem = ROOT / "data" / "dem" / "BharatRiskAI_WestBengal_DEM_GLO30.tif"
    if not default_dem.exists():
        default_dem = ROOT / "data" / "dem" / "kolkata_dem.tif"
    parser.add_argument("--dem", type=Path, default=default_dem)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "derived" / "terrain" / "dem_features.npz")
    args = parser.parse_args()
    build(args.dem, args.output)


if __name__ == "__main__":
    main()
