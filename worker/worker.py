import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from worker.tasks.alert_processing import process_alerts
from worker.tasks.report_processing import process_reports
from worker.tasks.risk_update import update_risk
from worker.tasks.weather_sync import sync_weather
from worker.tasks.satellite_sync import sync_satellite
from backend.config.settings import get_settings
import time


def run_once():
    return [sync_satellite(), update_risk(), process_reports(), process_alerts()]


if __name__ == "__main__":
    settings = get_settings()
    while True:
        print(run_once())
        time.sleep(settings.ingestion_interval_minutes * 60)

