"""Read-only audit of BharatRiskAI source data and scientific metadata."""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import rasterio

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGION = {"west": 85.7, "south": 21.5, "east": 89.9, "north": 27.2}
TIMESTAMP_PATTERN = re.compile(r"(\d{2}[A-Z]{3}\d{4})[_-](\d{4})", re.IGNORECASE)


def json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def attrs(value: Any) -> dict[str, Any]:
    return {str(key): json_value(item) for key, item in value.items()}


def timestamp_from_name(path: Path) -> str | None:
    match = TIMESTAMP_PATTERN.search(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%d%b%Y_%H%M").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def timestamp_from_attrs(file_attrs: dict[str, Any]) -> str | None:
    for key in ("Acquisition_Start_Time", "Acquisition_Time_in_GMT", "time"):
        value = file_attrs.get(key)
        if value is None:
            continue
        text = str(json_value(value))
        for fmt in ("%d-%b-%YT%H:%M:%S", "%d%b%Y_%H%M"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
    return None


def missing_percentage(dataset: h5py.Dataset) -> float | None:
    if not dataset.shape or dataset.size == 0 or not np.issubdtype(dataset.dtype, np.number):
        return None
    fill_values = [dataset.attrs.get(name) for name in ("_FillValue", "fill_value", "missing_value") if name in dataset.attrs]
    missing = 0
    total = 0
    for chunk in dataset.iter_chunks() if dataset.chunks else [tuple(slice(None) for _ in dataset.shape)]:
        values = np.asarray(dataset[chunk])
        invalid = ~np.isfinite(values)
        for fill in fill_values:
            try:
                invalid |= values == fill
            except TypeError:
                pass
        missing += int(invalid.sum())
        total += values.size
    return round(100.0 * missing / total, 6) if total else None


def dataset_record(dataset: h5py.Dataset, path: str) -> dict[str, Any]:
    return {
        "path": path,
        "shape": list(dataset.shape),
        "dtype": str(dataset.dtype),
        "units": json_value(dataset.attrs.get("units")),
        "fill_values": {name: json_value(dataset.attrs[name]) for name in ("_FillValue", "fill_value", "missing_value") if name in dataset.attrs},
        "scale_offset": {name: json_value(dataset.attrs[name]) for name in ("scale_factor", "add_offset", "lab_radiance_scale_factor", "lab_radiance_add_offset", "lab_radiance_quad", "lab_radiance_scale_factor_gsics", "lab_radiance_add_offset_gsics", "lab_radiance_quad_gsics") if name in dataset.attrs},
        "attributes": attrs(dataset.attrs),
        "missing_value_percentage": missing_percentage(dataset),
    }


def hdf5_record(path: Path) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        file_attrs = attrs(handle.attrs)
        datasets: list[dict[str, Any]] = []
        coordinate_datasets: list[str] = []
        def visit(name: str, value: Any) -> None:
            if isinstance(value, h5py.Dataset):
                datasets.append(dataset_record(value, name))
                if any(token in name.lower() for token in ("lat", "lon", "latitude", "longitude", "projection", "/x", "/y")):
                    coordinate_datasets.append(name)
        handle.visititems(visit)
    timestamp = timestamp_from_attrs(file_attrs) or timestamp_from_name(path)
    extent = {key: json_value(file_attrs[key]) for key in ("left_longitude", "right_longitude", "lower_latitude", "upper_latitude") if key in file_attrs}
    resolutions = [item.get("attributes", {}).get("resolution") for item in datasets if item.get("attributes", {}).get("resolution") is not None]
    return {
        "path": str(path.relative_to(ROOT)),
        "file_type": "HDF5",
        "size_bytes": path.stat().st_size,
        "timestamps": [timestamp] if timestamp else [],
        "spatial_extent": extent,
        "crs": file_attrs.get("crs") or file_attrs.get("projection"),
        "spatial_resolution": resolutions,
        "coordinate_structure": {"datasets": coordinate_datasets, "projected": any("projection" in item.lower() for item in coordinate_datasets)},
        "global_attributes": file_attrs,
        "variables": datasets,
    }


def raster_record(path: Path) -> dict[str, Any]:
    with rasterio.open(path) as dataset:
        values = dataset.read(masked=True)
        missing = float(values.mask.mean() * 100.0) if np.ma.isMaskedArray(values) else None
        return {
            "path": str(path.relative_to(ROOT)),
            "file_type": "GeoTIFF",
            "size_bytes": path.stat().st_size,
            "timestamps": [],
            "spatial_extent": {key: json_value(value) for key, value in zip(("left", "bottom", "right", "top"), dataset.bounds)},
            "crs": str(dataset.crs) if dataset.crs else None,
            "spatial_resolution": list(dataset.res),
            "coordinate_structure": {"transform": list(dataset.transform), "width": dataset.width, "height": dataset.height},
            "variables": [{"band": index, "dtype": dataset.dtypes[index - 1], "units": None, "fill_values": {"nodata": dataset.nodata}, "missing_value_percentage": missing} for index in range(1, dataset.count + 1)],
        }


def source_files(data_root: Path) -> list[Path]:
    return sorted(path for path in data_root.rglob("*") if path.is_file() and path.suffix.lower() in {".h5", ".hdf5", ".nc", ".nc4", ".netcdf", ".tif", ".tiff"})


def build_audit(data_root: Path) -> dict[str, Any]:
    records = []
    errors = []
    for path in source_files(data_root):
        try:
            if path.suffix.lower() in {".tif", ".tiff"}:
                records.append(raster_record(path))
            else:
                records.append(hdf5_record(path))
        except Exception as error:  # preserve failures in the report and continue auditing other files
            LOG.exception("Could not inspect %s", path)
            errors.append({"path": str(path.relative_to(ROOT)), "error": str(error)})
    timestamps = sorted({timestamp for record in records for timestamp in record.get("timestamps", [])})
    has_imdaa = any("imdaa" in record["path"].lower() for record in records)
    has_cmv = any("cmv" in record["path"].lower() for record in records)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "study_region": DEFAULT_REGION,
        "summary": {"file_count": len(records), "file_type_counts": {kind: sum(item["file_type"] == kind for item in records) for kind in ("HDF5", "GeoTIFF")}, "timestamp_count": len(timestamps), "timestamps": timestamps, "available_time_range": [timestamps[0], timestamps[-1]] if timestamps else [], "imdaa_available": has_imdaa, "cmv_available": has_cmv, "official_event_ground_truth_available": False, "official_flood_ground_truth_available": False},
        "records": records,
        "errors": errors,
        "readiness": {"missing_sources": [name for name, present in (("IMDAA", has_imdaa), ("CMV", has_cmv)) if not present], "missing_ground_truth": ["official thunderstorm/lightning events", "official cloudburst events", "official flood observations or inundation maps"], "label_policy": "Only proxy labels may be generated for hazards without observed ground truth; every proxy must carry provenance."},
    }


def write_reports(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "data_audit.json").write_text(json.dumps(json_value(report), indent=2, allow_nan=False), encoding="utf-8")
    summary = report["summary"]
    lines = ["BharatRiskAI dataset audit", "", f"Files: {summary['file_count']}", f"File types: {summary['file_type_counts']}", f"Timestamps: {summary['timestamp_count']}", f"Time range: {summary['available_time_range']}", f"IMDAA available: {summary['imdaa_available']}", f"CMV available: {summary['cmv_available']}", "", "Missing/blocked sources:"]
    lines.extend(f"- {item}" for item in report["readiness"]["missing_sources"] + report["readiness"]["missing_ground_truth"])
    lines.extend(["", "Files inspected:"])
    lines.extend(f"- {item['path']} ({item['file_type']}, {item['size_bytes']} bytes, {len(item.get('variables', []))} variables)" for item in report["records"])
    if report["errors"]:
        lines.extend(["", "Inspection errors:"] + [f"- {item['path']}: {item['error']}" for item in report["errors"]])
    (reports_dir / "data_audit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    write_reports(build_audit(args.data_root), args.reports_dir)


if __name__ == "__main__":
    main()
