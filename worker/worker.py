from worker.tasks.alert_processing import process_alerts
from worker.tasks.report_processing import process_reports
from worker.tasks.risk_update import update_risk
from worker.tasks.weather_sync import sync_weather


def run_once():
    return [sync_weather(), update_risk(), process_reports(), process_alerts()]


if __name__ == "__main__":
    print(run_once())
