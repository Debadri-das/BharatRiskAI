"""Standardize real INSAT QPE files; retain native mm/hr semantics and compute temporal accumulations."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]


def _process_single(path: Path) -> tuple[str | None, np.ndarray | None, dict | None]:
    try:
        from ingestion.real_data import read_qpe
        product = read_qpe(path)
        obs_time = str(product["observed_at"])
        values = np.asarray(product["qpe"], dtype=np.float32)
        valid = np.isfinite(product["latitude"]) & np.isfinite(product["longitude"])
        source_transform = from_bounds(
            float(np.nanmin(product["longitude"][valid])),
            float(np.nanmin(product["latitude"][valid])),
            float(np.nanmax(product["longitude"][valid])),
            float(np.nanmax(product["latitude"][valid])),
            values.shape[1],
            values.shape[0],
        )
        aligned = np.full((114, 84), np.nan, dtype=np.float32)
        reproject(
            values,
            aligned,
            src_transform=source_transform,
            src_crs="EPSG:4326",
            dst_transform=from_bounds(85.7, 21.5, 89.9, 27.2, 84, 114),
            dst_crs="EPSG:4326",
            src_nodata=-999.0,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
        aligned[aligned < 0] = np.nan
        return obs_time, aligned, None
    except Exception as exc:
        return None, None, {"path": str(path), "error": str(exc)}


def process_qpe(input_dir: Path, output_dir: Path) -> list[Path]:
    from ml.preprocessing.qpe import accumulate_rate

    files = sorted(input_dir.rglob("*.h5"))
    if not files:
        raise FileNotFoundError(f"No INSAT QPE HDF5 files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    products_by_time: dict[str, np.ndarray] = {}
    errors: list[dict[str, str]] = []

    print(f"Reading and reprojecting {len(files)} QPE files using parallel workers...")
    workers = min(8, os.cpu_count() or 4)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for idx, (obs_time, aligned, err) in enumerate(executor.map(_process_single, files), 1):
            if err:
                print(f"[WARNING] Skipping corrupt/unreadable file: {err['path']}: {err['error']}")
                errors.append(err)
            elif obs_time and obs_time not in products_by_time:
                products_by_time[obs_time] = aligned
            if idx % 200 == 0 or idx == len(files):
                print(f"  Processed [{idx}/{len(files)}] files...")

    products = sorted(products_by_time.items(), key=lambda item: item[0])
    times = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value, _ in products]
    rates = np.stack([value for _, value in products])
    output_files: list[Path] = []

    print(f"Computing accumulations for {len(products)} timestamps...")
    for index, (observed_at, aligned) in enumerate(products):
        # 24 steps is 12 hours, ample for the maximum 6-hour accumulation window
        start_idx = max(0, index - 24)
        sub_rates = rates[start_idx : index + 1]
        sub_times = times[start_idx : index + 1]

        accumulations = {
            hours: accumulate_rate(sub_rates, sub_times, hours)
            for hours in (1.0, 3.0, 6.0)
        }
        target = output_dir / f"qpe_{observed_at[:16].replace(':', '').replace('-', '').replace('T', '_')}.npz"
        np.savez_compressed(
            target,
            timestamp=observed_at,
            qpe_rate_mm_hr=aligned,
            qpe_1h_mm=accumulations[1.0].value,
            qpe_3h_mm=accumulations[3.0].value,
            qpe_6h_mm=accumulations[6.0].value,
            qpe_valid_mask=np.isfinite(aligned),
        )
        metadata = {
            "source": "INSAT-3DR HEM QPE",
            "timestamp": observed_at,
            "units": {
                "qpe_rate_mm_hr": "mm/hr",
                "qpe_1h_mm": "mm (sum_{i=1}^2 r_i Delta t_i, Delta t_i=0.5h)",
                "qpe_3h_mm": "mm (sum_{i=1}^6 r_i Delta t_i, Delta t_i=0.5h)",
                "qpe_6h_mm": "mm (sum_{i=1}^{12} r_i Delta t_i, Delta t_i=0.5h)",
            },
            "accumulation_status": {
                "1h": accumulations[1.0].status,
                "3h": accumulations[3.0].status,
                "6h": accumulations[6.0].status,
            },
            "valid_fraction": float(np.mean(np.isfinite(aligned))),
        }
        target.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        output_files.append(target)
        if (index + 1) % 200 == 0 or (index + 1) == len(products):
            print(f"  Saved [{index + 1}/{len(products)}] accumulation grids...")

    error_log_path = output_dir / "qpe_extraction_errors.json"
    error_log_path.write_text(json.dumps(errors, indent=2), encoding="utf-8")

    return output_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Standardize INSAT QPE products and compute accumulations")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "insat" / "qpe")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "derived" / "satellite")
    args = parser.parse_args()
    process_qpe(args.input, args.output)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
