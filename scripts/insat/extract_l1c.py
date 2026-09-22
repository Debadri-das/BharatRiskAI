"""Extract calibrated INSAT-3DR L1C channels into cropped NumPy products."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from rasterio.crs import CRS
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[2]
REGION = {"west": 85.7, "south": 21.5, "east": 89.9, "north": 27.2}
LOG = logging.getLogger(__name__)


def scalar(value: Any, default: float = 0.0) -> float:
    array = np.asarray(value)
    return float(array.reshape(-1)[0]) if array.size else default


def find_dataset(handle: h5py.File, name: str) -> h5py.Dataset:
    matches: list[h5py.Dataset] = []
    def visitor(path: str, value: Any) -> None:
        if isinstance(value, h5py.Dataset) and path.rsplit("/", 1)[-1] == name:
            matches.append(value)
    handle.visititems(visitor)
    if not matches:
        raise KeyError(f"Dataset {name!r} not found in {handle.filename}")
    return matches[0]


def calibration(dataset: h5py.Dataset) -> np.ndarray:
    counts = np.asarray(dataset[0] if dataset.ndim == 3 else dataset, dtype=np.float32)
    attrs = dataset.attrs
    fill = {scalar(attrs[name]) for name in ("_FillValue", "fill_value", "missing_value") if name in attrs}
    invalid = ~np.isfinite(counts) | (counts == 1023)
    for value in fill:
        invalid |= counts == value
    scale = scalar(attrs.get("lab_radiance_scale_factor", 1.0), 1.0)
    offset = scalar(attrs.get("lab_radiance_add_offset", 0.0), 0.0)
    quad = scalar(attrs.get("lab_radiance_quad", 0.0), 0.0)
    result = quad * counts * counts + scale * counts + offset
    result[invalid] = np.nan
    return result.astype(np.float32)


def lut_temperature(handle: h5py.File, channel: str, counts: np.ndarray) -> np.ndarray:
    count_dataset = find_dataset(handle, channel)
    raw = np.asarray(count_dataset[0] if count_dataset.ndim == 3 else count_dataset, dtype=np.float32)
    lut = np.asarray(find_dataset(handle, f"{channel}_TEMP")[:], dtype=np.float32)
    result = np.full(raw.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(raw) & (raw >= 0) & (raw < len(lut)) & (raw != 1023)
    result[valid] = lut[raw[valid].astype(np.int64)]
    return result


def source_crs(handle: h5py.File) -> CRS:
    projection = find_dataset(handle, "Projection_Information").attrs
    return CRS.from_dict({"proj": "merc", "lat_ts": scalar(projection["standard_parallel"], 17.75), "lon_0": scalar(projection["longitude_of_projection_origin"], 77.25), "a": scalar(projection["semi_major_axis"]), "b": scalar(projection["semi_minor_axis"]), "x_0": scalar(projection.get("false_easting", 0)), "y_0": scalar(projection.get("false_northing", 0))})


def read_timestamp(handle: h5py.File, path: Path) -> str:
    value = handle.attrs.get("Acquisition_Start_Time")
    if value is not None:
        text = value.decode() if isinstance(value, bytes) else str(value)
        return datetime.strptime(text, "%d-%b-%YT%H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    text = path.name.split("_")
    return datetime.strptime(f"{text[1]}_{text[2]}", "%d%b%Y_%H%M").replace(tzinfo=timezone.utc).isoformat()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def extract(path: Path, output_dir: Path, region: dict[str, float] = REGION) -> Path:
    with h5py.File(path, "r") as handle:
        x = np.asarray(find_dataset(handle, "X")[:], dtype=np.float64)
        y = np.asarray(find_dataset(handle, "Y")[:], dtype=np.float64)
        xx, yy = np.meshgrid(x, y)
        source = source_crs(handle)
        lon, lat = transform(source, CRS.from_epsg(4326), xx.ravel(), yy.ravel())
        lon = np.asarray(lon).reshape(xx.shape)
        lat = np.asarray(lat).reshape(yy.shape)
        mask = (lon >= region["west"]) & (lon <= region["east"]) & (lat >= region["south"]) & (lat <= region["north"])
        rows, cols = np.where(mask)
        if not len(rows):
            raise ValueError("Study region does not intersect the L1C product")
        row_slice = slice(rows.min(), rows.max() + 1)
        col_slice = slice(cols.min(), cols.max() + 1)
        channels = {
            "wv_radiance": calibration(find_dataset(handle, "IMG_WV"))[row_slice, col_slice],
            "tir1_bt_k": lut_temperature(handle, "IMG_TIR1", np.asarray(find_dataset(handle, "IMG_TIR1")[0], dtype=np.float32))[row_slice, col_slice],
            "tir2_bt_k": lut_temperature(handle, "IMG_TIR2", np.asarray(find_dataset(handle, "IMG_TIR2")[0], dtype=np.float32))[row_slice, col_slice],
            "vis_radiance": calibration(find_dataset(handle, "IMG_VIS"))[row_slice, col_slice],
        }
        # The visible product exposes a calibrated albedo LUT/product when present.
        try:
            albedo = find_dataset(handle, "IMG_VIS_ALBEDO")
            if albedo.ndim == 1:
                vis_counts = np.asarray(find_dataset(handle, "IMG_VIS")[0], dtype=np.float32)
                values = np.full(vis_counts.shape, np.nan, dtype=np.float32)
                valid = np.isfinite(vis_counts) & (vis_counts >= 0) & (vis_counts < albedo.shape[0]) & (vis_counts != 1023)
                values[valid] = np.asarray(albedo[:], dtype=np.float32)[vis_counts[valid].astype(np.int64)]
                channels["vis_albedo_percent"] = values[row_slice, col_slice]
            else:
                channels["vis_albedo_percent"] = np.asarray(albedo[0] if albedo.ndim == 3 else albedo, dtype=np.float32)[row_slice, col_slice]
        except KeyError:
            pass
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{path.stem}.npz"
        np.savez_compressed(target, timestamp=read_timestamp(handle, path), latitude=lat[row_slice, col_slice].astype(np.float32), longitude=lon[row_slice, col_slice].astype(np.float32), **channels)
        metadata = {"source": relative(path), "timestamp": read_timestamp(handle, path), "region": region, "source_crs": source.to_string(), "channels": list(channels), "calibration": "Radiance uses lab_radiance_quad + scale_factor*count + add_offset; TIR uses provider temperature LUT; WV remains radiance, not IWV."}
        target.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return target


def input_files(root: Path) -> list[Path]:
    candidates = sorted(root.rglob("*.h5"))
    selected: list[Path] = []
    seen_names: set[str] = set()
    for path in candidates:
        # Truncated/corrupt downloads are still selected so extract() fails loudly
        # and the failure lands in extraction_errors.json instead of being silently
        # skipped by a size heuristic.
        if path.name in seen_names:
            continue
        seen_names.add(path.name)
        selected.append(path)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "insat" / "l1c")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "insat" / "l1c" / "processed")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args.input = args.input.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    for path in input_files(args.input)[:args.limit]:
        try:
            LOG.info("Extracting %s", path.name)
            extract(path, args.output)
        except Exception as error:
            LOG.error("Skipping %s: %s", path, error)
            errors.append({"path": relative(path), "error": str(error)})
    # Always rewrite the error record so stale failures from earlier runs are cleared.
    (args.output / "extraction_errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
