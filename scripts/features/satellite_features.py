"""Build provenance-preserving satellite feature grids from standardized L1C products."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger(__name__)
CHANNELS = ["wv_radiance", "wv_change", "wv_rate", "wv_spatial_gradient", "tir1_bt_c", "tir2_bt_c", "ctt_change", "ctt_cooling_rate", "vis_radiance", "vis_albedo_percent"]


def target_grid() -> dict[str, Any]:
    return {"crs": rasterio.crs.CRS.from_epsg(4326), "transform": from_bounds(85.7, 21.5, 89.9, 27.2, 84, 114), "shape": (114, 84)}


def align(values: np.ndarray, latitude: np.ndarray, longitude: np.ndarray, grid: dict[str, Any], nearest: bool = False) -> np.ndarray:
    valid = np.isfinite(latitude) & np.isfinite(longitude) & (np.abs(latitude) <= 90) & (np.abs(longitude) <= 180)
    source_transform = from_bounds(float(np.nanmin(longitude[valid])), float(np.nanmin(latitude[valid])), float(np.nanmax(longitude[valid])), float(np.nanmax(latitude[valid])), values.shape[1], values.shape[0])
    output = np.full(grid["shape"], np.nan, dtype=np.float32)
    reproject(np.asarray(values, dtype=np.float32), output, src_transform=source_transform, src_crs="EPSG:4326", dst_transform=grid["transform"], dst_crs=grid["crs"], src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest if nearest else Resampling.bilinear)
    return output


def timestamp(path: Path) -> datetime:
    with np.load(path, allow_pickle=False) as data:
        return datetime.fromisoformat(str(data["timestamp"]))


def finite_mean(array: np.ndarray) -> float | None:
    values = array[np.isfinite(array)]
    return float(values.mean()) if values.size else None


def build(input_dir: Path, output_dir: Path) -> list[Path]:
    grid = target_grid()
    sources = sorted(input_dir.glob("*.npz"), key=timestamp)
    unique: dict[str, Path] = {}
    for source in sources:
        unique.setdefault(timestamp(source).isoformat(), source)
    previous: dict[str, np.ndarray] = {}
    previous_time: datetime | None = None
    outputs: list[Path] = []
    for current_time, source in sorted(unique.items()):
        with np.load(source, allow_pickle=False) as data:
            lat = data["latitude"]
            lon = data["longitude"]
            wv = align(data["wv_radiance"], lat, lon, grid)
            tir1 = align(data["tir1_bt_k"] - 273.15, lat, lon, grid)
            tir2 = align(data["tir2_bt_k"] - 273.15, lat, lon, grid)
            vis = align(data["vis_radiance"], lat, lon, grid)
            albedo = align(data["vis_albedo_percent"], lat, lon, grid) if "vis_albedo_percent" in data else np.full(grid["shape"], np.nan, dtype=np.float32)
        now = datetime.fromisoformat(current_time)
        elapsed_hours = (now - previous_time).total_seconds() / 3600 if previous_time else np.nan
        wv_change = wv - previous["wv"] if "wv" in previous else np.full(grid["shape"], np.nan, dtype=np.float32)
        ctt_change = tir1 - previous["ctt"] if "ctt" in previous else np.full(grid["shape"], np.nan, dtype=np.float32)
        wv_rate = wv_change / elapsed_hours if np.isfinite(elapsed_hours) and elapsed_hours > 0 else np.full(grid["shape"], np.nan, dtype=np.float32)
        ctt_cooling_rate = -ctt_change / elapsed_hours if np.isfinite(elapsed_hours) and elapsed_hours > 0 else np.full(grid["shape"], np.nan, dtype=np.float32)
        gradient_y, gradient_x = np.gradient(wv)
        feature_arrays = {"wv_radiance": wv, "wv_change": wv_change, "wv_rate": wv_rate, "wv_spatial_gradient": np.hypot(gradient_x, gradient_y), "tir1_bt_c": tir1, "tir2_bt_c": tir2, "ctt_change": ctt_change, "ctt_cooling_rate": ctt_cooling_rate, "vis_radiance": vis, "vis_albedo_percent": albedo}
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{now.strftime('%Y%m%d_%H%M')}.npz"
        np.savez_compressed(target, timestamp=current_time, **feature_arrays)
        target.with_suffix(".json").write_text(json.dumps({"source": str(source.relative_to(ROOT)), "timestamp": current_time, "grid": {"crs": "EPSG:4326", "shape": list(grid["shape"]), "resolution_degrees": [0.05, 0.05]}, "feature_semantics": {"wv_radiance": "calibrated INSAT WV radiance, not IWV", "wv_change": "current minus previous observed WV radiance", "tir1_bt_c": "INSAT TIR1 (10.8 um) brightness temperature in degrees Celsius; used only as a cloud-top temperature (CTT) proxy", "ctt_proxy_note": "CTT is a proxy: the TIR1 window channel approximates cloud-top temperature for optically thick clouds and is slightly warmer than true CTT. It is not a retrieved cloud-top temperature product.", "ctt_cooling_rate": "negative CTT-proxy change per elapsed observed hour; positive means cooling"}, "summary": {name: finite_mean(value) for name, value in feature_arrays.items()}}, indent=2), encoding="utf-8")
        outputs.append(target)
        previous = {"wv": wv, "ctt": tir1}
        previous_time = now
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "insat" / "l1c" / "processed")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "derived" / "satellite")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    outputs = build(args.input, args.output)
    LOG.info("Wrote %d satellite feature grids", len(outputs))


if __name__ == "__main__":
    main()
