"""Continuous ingestion orchestration and Supabase persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from backend.config.settings import get_settings
from backend.database.connection import get_supabase_admin_client
from ingestion.real_data import latest_file, read_dem, read_imdaa, read_insat


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
        "metadata": metadata,
    }, on_conflict="source,observed_at,variable").execute()


def ingest_latest() -> dict[str, Any]:
    settings = get_settings()
    client = get_supabase_admin_client()
    run = client.table("ingestion_runs").insert({"source": "multimodal", "status": "RUNNING"}).execute().data[0]
    files_processed = 0
    try:
        imdaa_path = latest_file(settings.imdaa_data_dir, (".nc", ".nc4", ".netcdf"))
        insat_path = latest_file(settings.insat_data_dir, (".nc", ".nc4", ".h5", ".hdf5"))
        dem_path = latest_file(settings.dem_data_dir, (".tif", ".tiff"))
        if not imdaa_path or not insat_path or not dem_path:
            missing = [name for name, path in (("IMDAA", imdaa_path), ("INSAT", insat_path), ("DEM", dem_path)) if path is None]
            raise FileNotFoundError(f"Missing latest data files: {', '.join(missing)}")

        imdaa = read_imdaa(imdaa_path)
        insat = read_insat(insat_path)
        dem = read_dem(dem_path)
        for source_data in (imdaa, insat, dem):
            source = source_data["source"]
            observed_at = source_data["observed_at"]
            for variable in ("iwv", "ctt", "qpe", "temperature", "u_wind", "v_wind", "elevation", "slope"):
                if variable in source_data:
                    _persist_grid(client, source, observed_at, variable, source_data[variable], source_data["metadata"])
            files_processed += 1

        client.table("ingestion_runs").update({"status": "SUCCEEDED", "finished_at": datetime.now(timezone.utc).isoformat(), "files_processed": files_processed}).eq("id", run["id"]).execute()
        return {"status": "SUCCEEDED", "files_processed": files_processed, "observed_at": insat["observed_at"]}
    except Exception as error:
        client.table("ingestion_runs").update({"status": "FAILED", "finished_at": datetime.now(timezone.utc).isoformat(), "files_processed": files_processed, "error": str(error)}).eq("id", run["id"]).execute()
        raise
