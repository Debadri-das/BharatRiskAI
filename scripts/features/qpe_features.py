"""Standardize real INSAT QPE files; retain the product's native mm/hr semantics."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    from ingestion.real_data import read_qpe
    files = sorted((ROOT / "data" / "insat" / "qpe").rglob("*.h5"))
    if not files:
        raise FileNotFoundError("No INSAT QPE HDF5 files found")
    output_dir = ROOT / "data" / "derived" / "satellite"
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        product = read_qpe(path)
        values = np.asarray(product["qpe"], dtype=np.float32)
        valid = np.isfinite(product["latitude"]) & np.isfinite(product["longitude"])
        source_transform = from_bounds(float(np.nanmin(product["longitude"][valid])), float(np.nanmin(product["latitude"][valid])), float(np.nanmax(product["longitude"][valid])), float(np.nanmax(product["latitude"][valid])), values.shape[1], values.shape[0])
        aligned = np.full((114, 84), np.nan, dtype=np.float32)
        reproject(values, aligned, src_transform=source_transform, src_crs="EPSG:4326", dst_transform=from_bounds(85.7, 21.5, 89.9, 27.2, 84, 114), dst_crs="EPSG:4326", src_nodata=-999.0, dst_nodata=np.nan, resampling=Resampling.nearest)
        target = output_dir / f"qpe_{product['observed_at'][:16].replace(':', '').replace('-', '').replace('T', '_')}.npz"
        np.savez_compressed(target, timestamp=product["observed_at"], qpe_rate_mm_hr=aligned, qpe_1h_mm=np.full_like(aligned, np.nan), qpe_3h_mm=np.full_like(aligned, np.nan), qpe_6h_mm=np.full_like(aligned, np.nan))
        target.with_suffix(".json").write_text(json.dumps({"source": str(path.relative_to(ROOT)), "units": "mm/hr", "aggregation": "1h/3h/6h unavailable because only one QPE timestamp is present; no temporal accumulation fabricated."}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
