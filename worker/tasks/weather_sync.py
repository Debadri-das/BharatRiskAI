from ingestion.pipeline import ingest_latest


def sync_weather():
    try:
        result = ingest_latest()
        return {"task": "weather_sync", **result}
    except FileNotFoundError as error:
        return {"task": "weather_sync", "status": "waiting_for_files", "error": str(error)}
    except Exception as error:
        return {"task": "weather_sync", "status": "failed", "error": str(error)}
