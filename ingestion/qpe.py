"""Filesystem-backed INSAT QPE ingestion."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

from ingestion.real_data import discover_tier1_files, read_qpe, validate_insat_npz


def extract_qpe_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    root = Path(os.getenv("BHARATRISK_DATA_ROOT", Path(__file__).resolve().parents[1]))
    records = []
    for path in discover_tier1_files(root)["qpe"]:
        if path.suffix.lower() == ".npz":
            validate_insat_npz(path, "qpe")
            with np.load(path, allow_pickle=False) as data:
                record = {"observed_at": str(data["timestamp"]), "latitude": data["latitude"], "longitude": data["longitude"], "qpe": data["qpe"] if "qpe" in data else data["qpe_rate_mm_hr"]}
        else:
            record = read_qpe(path)
        stamp = datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
        stamp = stamp.astimezone(timezone.utc) if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
        begin = start_time.astimezone(timezone.utc) if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        finish = end_time.astimezone(timezone.utc) if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
        if begin <= stamp <= finish:
            records.append((stamp, record))
    if not records:
        raise FileNotFoundError("No validated INSAT QPE products fall inside the requested time range")
    records.sort(key=lambda item: item[0])
    lat, lon = np.asarray(records[0][1]["latitude"]), np.asarray(records[0][1]["longitude"])
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("Canonical QPE ingestion requires one-dimensional latitude/longitude coordinates")
    values = np.stack([np.asarray(item[1]["qpe"], dtype=np.float64) for item in records])
    return xr.Dataset({"qpe": (("time", "lat", "lon"), values)}, coords={"time": [item[0] for item in records], "lat": lat, "lon": lon}, attrs={"source": "INSAT HEM", "qpe_units": "mm/hour"})
