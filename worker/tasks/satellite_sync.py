from ingestion.pipeline import ingest_latest


def sync_satellite():
    """Decode the newest MOSDAC/INSAT-3D/IMDAA products into Supabase."""
    try:
        return {"task": "satellite_sync", **ingest_latest()}
    except FileNotFoundError as error:
        return {"task": "satellite_sync", "status": "waiting_for_products", "error": str(error)}
    except Exception as error:
        return {"task": "satellite_sync", "status": "failed", "error": str(error)}
