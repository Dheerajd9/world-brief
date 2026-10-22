"""Docker scheduler: wake up every minute and do what is due, forever.

  - the edition (`run due`)            whenever something is due and not sent yet
  - the watchdog                       once an hour (it acts only at its own hour)
  - breaking alerts (if enabled)       every 2 hours

Each job runs in its own process, so one bad run can never stop the loop. State lives in
/data (mounted volume), so a restart never sends twice.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config

APP = Path(__file__).resolve().parent


def job(*args: str) -> int:
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] python -m app {' '.join(args)}", flush=True)
    try:
        return subprocess.run([sys.executable, "-m", "app", *args], cwd=APP.parent,
                              timeout=3 * 3600).returncode
    except subprocess.TimeoutExpired:
        print("  ! job took over 3 hours; stopped", flush=True)
        return 1


def main(max_loops: int | None = None, sleep=time.sleep) -> int:
    cfg = config.apply()
    tz = ZoneInfo(cfg["you"]["timezone"])
    print(f"World Brief scheduler started: {cfg['email']['send_time']} {cfg['you']['timezone']}, "
          f"state in {os.getenv('WB_DATA') or APP.parent}", flush=True)
    last_watch, last_alert, last_due_try = None, None, 0.0
    loops = 0
    while max_loops is None or loops < max_loops:
        loops += 1
        now = datetime.now(tz)
        if time.monotonic() - last_due_try > 15 * 60 or last_due_try == 0.0:
            # `run due` exits in a second when nothing is due; retry a failed edition every 15 min
            last_due_try = time.monotonic()
            job("run", "due")
        hour_key = now.strftime("%Y-%m-%d %H")
        if last_watch != hour_key and now.minute >= 5:
            last_watch = hour_key
            job("watchdog")
        if cfg["alerts"]["breaking"] and now.hour % 2 == 0 and last_alert != hour_key:
            last_alert = hour_key
            job("alerts")
        sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
