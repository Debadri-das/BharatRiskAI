"""Filesystem-backed INSAT feature ingestion."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

from ingestion.real_data import discover_tier1_files, validate_insat_npz


def _root() -> Path:
    return Path(os.getenv("BHARATRISK_DATA_ROOT", Path(__file__).resolve().parents[1]))


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def extract_insat_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    """Read validated extracted L1C NPZ files and derive CTT/cooling rate."""
    files = discover_tier1_files(_root())
    candidates = sorted(set(files["wv"]) & set(files["tir"]))
    if not candidates:
        raise FileNotFoundError("No extracted INSAT file containing both WV and TIR products was discovered")
    frames = []
    for path in candidates:
        validate_insat_npz(path, "wv")
        validate_insat_npz(path, "tir")
        with np.load(path, allow_pickle=False) as data:
            stamp = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
            stamp = _utc(stamp)
            if not (_utc(start_time) <= stamp <= _utc(end_time)):
                continue
            lat, lon = np.asarray(data["latitude"]), np.asarray(data["longitude"])
            tir = np.asarray(data["tir1_bt_k"], dtype=np.float64)
            if lat.ndim == lon.ndim == 1:
                ymask = (lat >= bbox[1]) & (lat <= bbox[3])
                xmask = (lon >= bbox[0]) & (lon <= bbox[2])
                tir, lat, lon = tir[np.ix_(ymask, xmask)], lat[ymask], lon[xmask]
            frames.append((stamp, lat, lon, tir - 273.15))
    if not frames:
        raise FileNotFoundError("No validated INSAT WV/TIR frames fall inside the requested time range")
    frames.sort(key=lambda item: item[0])
    shapes = {item[3].shape for item in frames}
    if len(shapes) != 1:
        raise ValueError(f"INSAT frames do not share one grid: {sorted(shapes)}")
    ctt = np.stack([item[3] for item in frames])
    cooling = np.zeros_like(ctt)
    for index in range(1, len(frames)):
        hours = (frames[index][0] - frames[index - 1][0]).total_seconds() / 3600
        if hours <= 0:
            raise ValueError("INSAT timestamps must be unique and increasing")
        cooling[index] = -(ctt[index] - ctt[index - 1]) / hours
    lat, lon = frames[0][1], frames[0][2]
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("Canonical INSAT feature ingestion requires one-dimensional latitude/longitude coordinates")
    return xr.Dataset(
        {"ctt": (("time", "lat", "lon"), ctt), "ctt_drop_rate": (("time", "lat", "lon"), cooling)},
        coords={"time": [item[0] for item in frames], "lat": lat, "lon": lon},
        attrs={"source": "INSAT-3DR filesystem products", "ctt_units": "degrees_C", "ctt_drop_rate_units": "degrees_C/hour"},
    )
