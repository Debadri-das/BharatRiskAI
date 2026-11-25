"""Automated daily batch downloader for MOSDAC data across 180 days.

Iterates through daily windows from 2020-04-02 to 2020-09-27,
updating config.json and triggering mdapi.py for each day.
"""
from __future__ import annotations

import argparse
import datetime
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

# Force IPv4 to bypass unreachable MOSDAC IPv6 route
_orig_gai = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_gai(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

DIR = Path(__file__).resolve().parent


def run_automation(start: datetime.date, end: datetime.date, dataset_id: str | None = None) -> None:
    config_path = DIR / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config.json at {config_path}")

    current_date = start
    delta = datetime.timedelta(days=1)
    total_days = (end - start).days + 1
    day_idx = 0

    print("=======================================================")
    print(f" MOSDAC AUTOMATED BATCH DOWNLOADER")
    print(f" Range: {start} to {end} ({total_days} days)")
    if dataset_id:
        print(f" Dataset override: {dataset_id}")
    print("=======================================================\n")

    while current_date <= end:
        day_idx += 1
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n=======================================================")
        print(f" [{day_idx}/{total_days}] FETCHING DATA FOR: {date_str}")
        print(f"=======================================================\n")

        # 1. Read existing config
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 2. Check credentials
        creds = config.get("user_credentials", {})
        username = creds.get("username") or creds.get("username/email") or ""
        password = creds.get("password") or ""
        if "YOUR_MOSDAC" in username or "YOUR_MOSDAC" in password or not username or not password:
            print("\n[ERROR] Real MOSDAC credentials not configured in config.json!")
            print("Please open mosdac_downloader/config.json and set your username and password.")
            sys.exit(1)

        # 3. Update date parameters
        config["search_parameters"]["startTime"] = date_str
        config["search_parameters"]["endTime"] = date_str
        if dataset_id:
            config["search_parameters"]["datasetId"] = dataset_id
            if "L1C" in dataset_id:
                config["download_settings"]["download_path"] = "C:/Users/dasde/BharatRiskAI/data/insat/l1c"
            elif "L2B" in dataset_id or "HEM" in dataset_id or "QPE" in dataset_id:
                config["download_settings"]["download_path"] = "C:/Users/dasde/BharatRiskAI/data/insat/qpe"

        # 4. Save updated config
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        # 5. Execute mdapi.py in downloader directory with up to 3 retries
        success = False
        for attempt in range(1, 4):
            try:
                result = subprocess.run([sys.executable, "-u", "mdapi.py"], cwd=DIR, check=False)
                if result.returncode == 0:
                    success = True
                    break
                else:
                    print(f"[WARNING] mdapi.py exited with code {result.returncode} on {date_str} (Attempt {attempt}/3). Retrying in 10s...")
                    time.sleep(10)
            except Exception as exc:
                print(f"[ERROR] Failed to execute mdapi.py on {date_str} (Attempt {attempt}/3): {exc}. Retrying in 10s...")
                time.sleep(10)

        if not success:
            print(f"[ALERT] Could not complete all passes for {date_str} after 3 attempts. Moving to next day...")

        # 6. Move to next day
        current_date += delta

    print("\n🎉 Automated Download Loop Complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated MOSDAC daily batch downloader")
    parser.add_argument("--start", type=str, default="2020-04-02", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2020-09-27", help="End date (YYYY-MM-DD)")
    parser.add_argument("--dataset", type=str, default=None, help="Dataset ID override (e.g. 3RIMG_L1C_ASIA_MER or 3RIMG_L2B_HEM)")
    args = parser.parse_args()

    start_date = datetime.date.fromisoformat(args.start)
    end_date = datetime.date.fromisoformat(args.end)
    run_automation(start_date, end_date, args.dataset)


if __name__ == "__main__":
    main()
