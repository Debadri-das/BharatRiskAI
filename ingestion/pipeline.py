"""Continuous ingestion orchestration and Supabase persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from backend.config.settings import get_settings
from backend.database.connection import get_supabase_admin_client
from ingestion.real_data import align_to_grid, cape_cin, latest_file, read_dem, read_imdaa, read_insat, read_qpe, target_grid, temporal_change, wind_diagnostics


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.round(6).tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _persist_grid(client: Any, source: str, observed_at: str, variable: str, values: Any, metadata: dict[str, Any]) -> None:
    array = np.asarray(values)
    client.table("grid_observations").upsert({
        "source": source,
        "observed_at": observed_at,
        "variable": variable,
        "units": metadata.get("units"),
        "shape": list(array.shape),
        "values": _json_value(array),
        "metadata": {**metadata, "finite_fraction": float(np.isfinite(array).mean()) if array.size else 0.0},
    }, on_conflict="source,observed_at,variable").execute()


def ingest_latest() -> dict[str, Any]:
    settings = get_settings()
    client = get_supabase_admin_client()
    run = client.table("ingestion_runs").insert({"source": "multimodal", "status": "RUNNING"}).execute().data[0]
    files_processed = 0
    try:
        imdaa_path = latest_file(settings.imdaa_data_dir, (".nc", ".nc4", ".netcdf"))
        insat_path = latest_file(Path(settings.insat_data_dir) / "ir" / "raw", (".nc", ".nc4", ".h5", ".hdf5")) or latest_file(settings.insat_data_dir, (".nc", ".nc4", ".h5", ".hdf5"))
        qpe_path = latest_file(Path(settings.insat_data_dir) / "qpe" / "raw", (".nc", ".nc4", ".h5", ".hdf5")) or latest_file(Path(settings.insat_data_dir) / "qpe", (".nc", ".nc4", ".h5", ".hdf5"))
        dem_path = latest_file(settings.dem_data_dir, (".tif", ".tiff"))
        if not insat_path or not dem_path:
            missing = [name for name, path in (("INSAT", insat_path), ("DEM", dem_path)) if path is None]
            raise FileNotFoundError(f"Missing latest data files: {', '.join(missing)}")

        insat = read_insat(insat_path)
        dem = read_dem(dem_path)
        grid = target_grid(dem_path)
        for name in ("ctt", "qpe"):
            if name in insat:
                insat[name] = align_to_grid(insat[name], insat["latitude"], insat["longitude"], grid, nearest=name == "qpe")
        sources = [insat, dem]
        if qpe_path and qpe_path != insat_path:
            qpe = read_qpe(qpe_path)
            qpe["qpe"] = align_to_grid(qpe["qpe"], qpe["latitude"], qpe["longitude"], grid, nearest=True)
            sources.append(qpe)
        if imdaa_path:
            imdaa = read_imdaa(imdaa_path)
            imdaa["cape"], imdaa["cin"] = cape_cin(imdaa["temperature"], imdaa["specific_humidity"], imdaa["pressure_pa"])
            for name in ("iwv", "temperature", "u_wind", "v_wind", "cape", "cin"):
                if name in imdaa and np.asarray(imdaa[name]).ndim >= 2:
                    imdaa[name] = align_to_grid(np.nanmean(imdaa[name], axis=0) if np.asarray(imdaa[name]).ndim > 2 else imdaa[name], imdaa["latitude"], imdaa["longitude"], grid)
            if "u_wind" in imdaa and "v_wind" in imdaa:
                imdaa["convergence"], imdaa["wind_shear"] = wind_diagnostics(imdaa["u_wind"], imdaa["v_wind"], imdaa["latitude"], imdaa["longitude"])
            sources.append(imdaa)

        previous: dict[str, np.ndarray] = {}
        for source_data in sources:
            source = source_data["source"]
            observed_at = source_data["observed_at"]
            for variable in ("iwv", "ctt", "qpe", "temperature", "u_wind", "v_wind", "cape", "cin", "convergence", "wind_shear", "elevation", "slope", "sst"):
                if variable in source_data:
                    metadata = {**source_data["metadata"], "grid": {"crs": str(grid["crs"]), "shape": list(grid["shape"]), "transform": list(grid["transform"])[:6]}}
                    _persist_grid(client, source, observed_at, variable, source_data[variable], metadata)
                    current = np.asarray(source_data[variable], dtype=np.float64)
                    if variable in ("iwv", "ctt") and variable in previous:
                        rate_name = "iwv_change" if variable == "iwv" else "ctt_cooling_rate"
                        rate = temporal_change(current, previous[variable], 1.0)
                        if variable == "ctt":
                            rate = -rate
                        _persist_grid(client, source, observed_at, rate_name, rate, {**metadata, "derived_from": variable, "units": "per_hour"})
                    previous[variable] = current
            files_processed += 1

        client.table("ingestion_runs").update({"status": "SUCCEEDED", "finished_at": datetime.now(timezone.utc).isoformat(), "files_processed": files_processed}).eq("id", run["id"]).execute()
        return {"status": "SUCCEEDED", "files_processed": files_processed, "observed_at": insat["observed_at"]}
    except Exception as error:
        client.table("ingestion_runs").update({"status": "FAILED", "finished_at": datetime.now(timezone.utc).isoformat(), "files_processed": files_processed, "error": str(error)}).eq("id", run["id"]).execute()
        raise

