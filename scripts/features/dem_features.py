"""Derive supported terrain features from the DEM without fabricating drainage."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]


def build(dem_path: Path, output: Path) -> Path:
    with rasterio.open(dem_path) as source:
        elevation = np.full((114, 84), np.nan, dtype=np.float32)
        destination_transform = from_bounds(85.7, 21.5, 89.9, 27.2, 84, 114)
        reproject(source.read(1).astype(np.float32), elevation, src_transform=source.transform, src_crs=source.crs, dst_transform=destination_transform, dst_crs="EPSG:4326", src_nodata=source.nodata, dst_nodata=np.nan, resampling=Resampling.bilinear)
    lat_step = np.deg2rad(0.05) * 6_371_000.0
    lon_step = np.deg2rad(0.05) * 6_371_000.0 * np.cos(np.deg2rad(24.35))
    gradient_y, gradient_x = np.gradient(elevation, lat_step, lon_step)
    slope = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y)))
    aspect = (np.degrees(np.arctan2(-gradient_x, gradient_y)) + 360.0) % 360.0
    gradient = np.hypot(gradient_x, gradient_y)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, elevation=elevation, slope=slope.astype(np.float32), aspect=aspect.astype(np.float32), terrain_gradient=gradient.astype(np.float32))
    output.with_suffix(".json").write_text(json.dumps({"source": str(dem_path.relative_to(ROOT)), "grid": {"crs": "EPSG:4326", "shape": [114, 84], "resolution_degrees": [0.05, 0.05]}, "drainage": {"status": "unavailable", "reason": "No robust hydrological-flow implementation or hydrologic conditioning data is configured."}}, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    build(ROOT / "data" / "dem" / "kolkata_dem.tif", ROOT / "data" / "derived" / "terrain" / "dem_features.npz")
