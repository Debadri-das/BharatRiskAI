"""Wait for MOSDAC server availability and resume May 2020 L1C download."""
import datetime
import subprocess
import sys
import time
import requests

URL = "https://mosdac.gov.in"
MAX_ATTEMPTS = 500  # Poll for up to 4+ hours
INTERVAL = 30       # Check every 30 seconds

print("=======================================================", flush=True)
print(" MOSDAC AUTO-RETRY WATCHER: MAY 2020 L1C (MAY 24 - 31)", flush=True)
print("=======================================================\n", flush=True)

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        r = requests.get(URL, timeout=8)
        if r.status_code == 200 or r.status_code // 100 in [2, 3, 4]:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] MOSDAC is ONLINE (Status: {r.status_code})! Resuming download...", flush=True)
            cmd = [
                sys.executable,
                "mosdac_downloader/auto_download.py",
                "--start", "2020-05-24",
                "--end", "2020-05-31",
                "--dataset", "3RIMG_L1C_ASIA_MER"
            ]
            res = subprocess.run(cmd)
            if res.returncode == 0:
                print("\n🎉 May 2020 L1C Download Successfully Completed!", flush=True)
                sys.exit(0)
            else:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Downloader exited with code {res.returncode}. Retrying...", flush=True)
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Attempt {attempt}/{MAX_ATTEMPTS}: MOSDAC server unreachable ({type(e).__name__}). Retrying in {INTERVAL}s...", flush=True)
    time.sleep(INTERVAL)

print("\n[TIMEOUT] Max wait time reached. Server remained unreachable.", flush=True)
sys.exit(1)
