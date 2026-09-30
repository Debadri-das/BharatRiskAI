"""Filesystem-backed SRTM/NASADEM feature ingestion."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

from ingestion.real_data import discover_tier1_files, read_dem, validate_dem_file


def extract_dem_features(bbox: List[float]) -> xr.Dataset:
    root = Path(os.getenv("BHARATRISK_DATA_ROOT", Path(__file__).resolve().parents[1]))
    files = discover_tier1_files(root)["terrain"]
    if not files:
        raise FileNotFoundError("No SRTM/NASADEM GeoTIFF was discovered")
    path = files[0]
    validate_dem_file(path)
    product = read_dem(path)
    transform = product["metadata"]["transform"]
    height, width = product["elevation"].shape
    lon = transform[2] + (np.arange(width) + 0.5) * transform[0]
    lat = transform[5] + (np.arange(height) + 0.5) * transform[4]
    ymask = (lat >= bbox[1]) & (lat <= bbox[3])
    xmask = (lon >= bbox[0]) & (lon <= bbox[2])
    if not ymask.any() or not xmask.any():
        raise ValueError("Requested bounding box does not intersect the DEM")
    # Drainage is intentionally absent: it requires a separate conditioned
    # hydrology product and the canonical pipeline will report it as missing.
    return xr.Dataset(
        {"elevation": (("lat", "lon"), product["elevation"][np.ix_(ymask, xmask)]), "slope": (("lat", "lon"), product["slope"][np.ix_(ymask, xmask)])},
        coords={"lat": lat[ymask], "lon": lon[xmask]}, attrs={"source": str(path), "elevation_units": "metres", "slope_units": "degrees"}
    )
