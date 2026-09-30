"""Filesystem-backed IMDAA profile feature ingestion."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import List

import numpy as np
import xarray as xr

from ingestion.real_data import cape_cin, discover_tier1_files, read_imdaa, wind_diagnostics


def extract_imdaa_features(bbox: List[float], start_time: datetime, end_time: datetime) -> xr.Dataset:
    root = Path(os.getenv("BHARATRISK_DATA_ROOT", Path(__file__).resolve().parents[1]))
    records = []
    begin = start_time.astimezone(timezone.utc) if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
    finish = end_time.astimezone(timezone.utc) if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
    for path in discover_tier1_files(root)["imdaa"]:
        item = read_imdaa(path)
        stamp = datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
        stamp = stamp.astimezone(timezone.utc) if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
        if begin <= stamp <= finish:
            records.append((stamp, item))
    if not records:
        raise FileNotFoundError("No validated IMDAA profiles fall inside the requested time range")
    records.sort(key=lambda item: item[0])
    lat, lon = records[0][1]["latitude"], records[0][1]["longitude"]
    if lat.ndim != 1 or lon.ndim != 1:
        raise ValueError("Canonical IMDAA ingestion requires one-dimensional latitude/longitude coordinates")
    ymask, xmask = (lat >= bbox[1]) & (lat <= bbox[3]), (lon >= bbox[0]) & (lon <= bbox[2])
    features = {name: [] for name in ("iwv", "rainfall", "cape", "cin", "convergence", "wind_shear")}
    for _, item in records:
        if "rainfall" not in item:
            raise ValueError("IMDAA profile has no provider rainfall variable; rainfall will not be fabricated")
        cape, cin = cape_cin(item["temperature"], item["specific_humidity"], item["pressure_pa"])
        # Lowest model level diagnostics and full-column vector wind difference.
        convergence, _ = wind_diagnostics(item["u_wind"][0], item["v_wind"][0], lat[:, None] * np.ones((1, lon.size)), np.ones((lat.size, 1)) * lon)
        shear = np.hypot(item["u_wind"][-1] - item["u_wind"][0], item["v_wind"][-1] - item["v_wind"][0])
        values = {"iwv": item["iwv"], "rainfall": item["rainfall"], "cape": cape, "cin": cin, "convergence": convergence, "wind_shear": shear}
        for name, value in values.items():
            features[name].append(value[np.ix_(ymask, xmask)])
    iwv = np.stack(features["iwv"])
    iwv_change = np.zeros_like(iwv)
    for index in range(1, len(records)):
        hours = (records[index][0] - records[index - 1][0]).total_seconds() / 3600
        if hours <= 0:
            raise ValueError("IMDAA timestamps must be unique and increasing")
        iwv_change[index] = (iwv[index] - iwv[index - 1]) / hours
    variables = {name: (("time", "lat", "lon"), np.stack(value)) for name, value in features.items()}
    variables["iwv_change"] = (("time", "lat", "lon"), iwv_change)
    return xr.Dataset(variables, coords={"time": [item[0] for item in records], "lat": lat[ymask], "lon": lon[xmask]}, attrs={"source": "IMDAA filesystem profiles"})
