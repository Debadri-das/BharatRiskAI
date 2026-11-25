"""Optimized parallel batch derivation of June 2020 IMDAA atmospheric features."""
import concurrent.futures
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import xarray as xr
import numpy as np
from scripts.atmosphere.derive_features import derive_profile_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("imdaa_june_batch")

IMDAA_DIR = ROOT / "data" / "imdaa"
OUTPUT_DIR = ROOT / "data" / "processed" / "atmospheric_features"

LEVELS = ["1000mb", "925mb", "850mb", "600mb", "500mb", "400mb", "300mb", "200mb"]
VARS_MAP = {"t": "TMP", "r": "RH", "u": "UGRD", "v": "VGRD", "gh": "HGT"}

_INDEX = None


def get_file_index():
    global _INDEX
    if _INDEX is None:
        idx = {}
        for f in IMDAA_DIR.glob("*.nc*"):
            m = re.match(r"([A-Z]+-[0-9]+mb)_(\d{10})_", f.name)
            if m:
                idx[(m.group(1), m.group(2))] = f
        _INDEX = idx
    return _INDEX


def process_timestamp(ts: str) -> dict:
    try:
        dt = datetime.strptime(ts, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        out_file = OUTPUT_DIR / f"atmospheric_{dt.strftime('%Y%m%dT%H%M%SZ')}.nc"
        
        if out_file.exists() and out_file.stat().st_size > 10000:
            return {"timestamp": ts, "status": "SKIPPED_EXISTING", "output": str(out_file)}
            
        index = get_file_index()
        ds_levels = []
        for lvl in LEVELS:
            ds_vars = []
            for var_name, prefix in VARS_MAP.items():
                fname = index.get((f"{prefix}-{lvl}", ts))
                if fname is None:
                    return {"timestamp": ts, "status": "MISSING_VAR", "detail": f"Missing {prefix}-{lvl}"}
                ds_vars.append(xr.open_dataset(fname, engine="h5netcdf"))
            merged_lvl = xr.merge(ds_vars)
            ds_levels.append(merged_lvl)
            
        full_ds = xr.concat(ds_levels, dim="plev")
        
        # Efficient domain cropping (buffer around West Bengal target: 85.7-89.9 E, 21.5-27.2 N)
        lat_coord = next((c for c in ("latitude", "lat") if c in full_ds.coords), None)
        lon_coord = next((c for c in ("longitude", "lon") if c in full_ds.coords), None)
        if lat_coord and lon_coord:
            lats = full_ds[lat_coord].values
            lons = full_ds[lon_coord].values
            lat_mask = (lats >= 20.8) & (lats <= 28.0)
            lon_mask = (lons >= 85.0) & (lons <= 90.5)
            full_ds = full_ds.isel({lat_coord: lat_mask, lon_coord: lon_mask})
            
        res = derive_profile_dataset(full_ds)
        
        # Save compressed NetCDF via h5netcdf
        res.to_netcdf(out_file, engine="h5netcdf")
        
        for lvl_ds in ds_levels:
            lvl_ds.close()
        full_ds.close()
        
        return {"timestamp": ts, "status": "ACCEPTED", "output": str(out_file)}
    except Exception as e:
        return {"timestamp": ts, "status": "ERROR", "reason": str(e)}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    idx = get_file_index()
    logger.info(f"Indexed {len(idx)} IMDAA files in memory.")
    
    stamps = set()
    for (var_lvl, ts) in idx.keys():
        if ts.startswith("202006") and var_lvl == "TMP-1000mb":
            stamps.add(ts)
            
    sorted_stamps = sorted(stamps)
    logger.info(f"Discovered {len(sorted_stamps)} 3-hourly timestamps for June 2020.")
    if not sorted_stamps:
        logger.warning("No June 2020 IMDAA timestamps found in data/imdaa/. Please stage June 2020 NCMRWF NetCDFs in data/imdaa/.")
        return
        
    t0 = time.time()
    results = []
    
    max_workers = 4
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(process_timestamp, ts): ts for ts in sorted_stamps}
        completed_count = 0
        for future in concurrent.futures.as_completed(future_map):
            res = future.result()
            results.append(res)
            completed_count += 1
            if completed_count % 20 == 0 or completed_count == len(sorted_stamps):
                accepted = sum(1 for r in results if r["status"] in ("ACCEPTED", "SKIPPED_EXISTING"))
                rate = completed_count / max(time.time() - t0, 0.1)
                logger.info(f"Progress: {completed_count}/{len(sorted_stamps)} completed ({accepted} accepted) [{rate:.2f} timestamps/s]")
                
    dt = time.time() - t0
    accepted = sum(1 for r in results if r["status"] in ("ACCEPTED", "SKIPPED_EXISTING"))
    errors = sum(1 for r in results if r["status"] == "ERROR")
    logger.info(f"Completed June IMDAA derivation: {accepted} accepted, {errors} errors in {dt:.1f}s.")
    
    manifest_path = OUTPUT_DIR / "atmospheric_feature_manifest.json"
    existing_records = []
    if manifest_path.exists():
        try:
            existing_records = json.loads(manifest_path.read_text(encoding="utf-8")).get("records", [])
        except Exception:
            pass
    # Merge existing and new
    all_records = {r.get("timestamp"): r for r in existing_records}
    for r in results:
        all_records[r.get("timestamp")] = r
    manifest = {"schema_version": "atmospheric-v1", "records": list(all_records.values())}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"ALL_COMPLETED: {accepted} profiles generated.")


if __name__ == "__main__":
    main()
