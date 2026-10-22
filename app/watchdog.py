"""Watchdog: keeps the whole system healthy without anyone looking.

1. Missing-email alarm: 7 hours after your send time (config.yaml), if today's morning email
   (or the Sunday weekly) was never sent, alert the owner by email (+ personal Telegram chat).
   Catches the silent case where nothing ran at all.
2. Every Sunday: tests every news feed (feedcheck.py). A feed that is dead or empty two Sundays
   in a row is switched off automatically (state/feeds_disabled.json); a short report is
   emailed when something was switched off or too few feeds still work.

Sends nothing on a normal day. Never prints secrets.
"""

from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
DATA = Path(os.getenv("WB_DATA") or Path(__file__).resolve().parent.parent)   # state, briefs, logs (Docker: /data)
import config  # noqa: E402

CFG = config.apply()
TZ = ZoneInfo(os.getenv("BRIEF_TZ") or "UTC")
HEALTH = DATA / "state" / "feed_health.json"
DISABLED = DATA / "state" / "feeds_disabled.json"
BAD_WEEKS = 2            # dead/empty this many Sundays in a row -> switched off
MIN_OK_SHARE = 0.7       # fewer working feeds than this share -> warning email


def alert(subject: str, body: str) -> None:
    """Email (TO_EMAIL) + personal Telegram chat if set. Never raises."""
    user, pwd, to = (os.getenv(k, "").strip() for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "TO_EMAIL"))
    if user and pwd and to:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = subject, user, to
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
                s.login(user, pwd)
                s.sendmail(user, [a.strip() for a in to.split(",") if a.strip()], msg.as_string())
            print("alert emailed")
        except Exception as exc:
            print(f"could not email alert: {type(exc).__name__}")
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat:
        try:
            import requests
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                              json={"chat_id": chat, "text": f"{subject}\n\n{body}",
                                    "disable_web_page_preview": True})
            print(f"Telegram alert: HTTP {r.status_code}")
        except Exception as exc:      # the URL holds the bot token: print only the error type
            print(f"could not send Telegram alert: {type(exc).__name__}")


def missing(now: datetime) -> list[str]:
    """What should have been sent by now today but wasn't."""
    d = now.strftime("%Y-%m-%d")
    done = DATA / "state" / "done"
    out = []
    if not (done / f"{d}-morning").exists():
        out.append("morning email")
    if now.isoweekday() == 7 and os.getenv("WB_WEEKLY", "1") == "1" and not (done / f"{d}-weekly").exists():
        out.append("Sunday weekly")
    return out


def check_hour() -> int:
    return (int(str(os.getenv("WB_SEND_TIME", "07:00")).split(":")[0]) + 7) % 24


def check_sent(now: datetime) -> list[str]:
    miss = missing(now)
    if miss:
        alert(f"⏰ World Brief not sent today: {', '.join(miss)}",
              "These were not sent today:\n- " + "\n- ".join(miss)
              + "\n\nUsually the scheduler did not run (GitHub sometimes skips scheduled runs) or a "
              "run failed. To send now: GitHub -> Actions -> World Brief -> Run workflow -> "
              "morning (Docker: `docker compose run --rm world-brief run morning`)."
              + (f"\n\nDetails: {os.getenv('RUN_URL')}" if os.getenv("RUN_URL") else ""))
    else:
        print("all of today's emails were sent")
    return miss


def prune_feeds(rows: list[dict], health: dict) -> tuple[dict, list[str]]:
    """Count bad Sundays per feed; switch off feeds bad BAD_WEEKS Sundays in a row.
    If over a quarter of all feeds look bad, it's a network problem: count nothing."""
    bad = {r["url"] for r in rows if r["status"] in ("dead", "empty")}
    if len(bad) > len(rows) / 4:
        print(f"{len(bad)} of {len(rows)} feeds bad: looks like a network problem, nothing counted")
        return health, []
    new = {u: health.get(u, 0) + 1 for u in bad}
    removed = [u for u, n in new.items() if n >= BAD_WEEKS]
    for u in removed:
        new.pop(u)
    return new, removed


def check_feeds() -> None:
    import feedcheck
    rows = feedcheck.check(config.feeds(CFG))
    try:
        health = json.loads(HEALTH.read_text())
    except Exception:
        health = {}
    health, removed = prune_feeds(rows, health)
    (DATA / "logs").mkdir(parents=True, exist_ok=True)
    (DATA / "logs" / "feedcheck.txt").write_text(feedcheck.report(rows) + "\n")
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps(health, indent=1))
    if removed:
        try:
            off = json.loads(DISABLED.read_text())
        except Exception:
            off = []
        DISABLED.write_text(json.dumps(sorted(set(off) | set(removed)), indent=1))
    ok = sum(r["status"] == "ok" for r in rows)
    print(f"feeds: {len(rows)}, ok {ok}, bad this week {len(health)}, switched off {len(removed)}")
    if removed or ok < MIN_OK_SHARE * len(rows):
        alert(f"📰 Weekly feed check: {ok} of {len(rows)} news feeds working",
              (("Switched off (dead or empty two Sundays in a row):\n- " + "\n- ".join(removed) + "\n\n")
               if removed else "")
              + (f"Only {ok} feeds work now. Add sources in config.yaml (feeds_extra).\n"
                 if ok < MIN_OK_SHARE * len(rows) else "")
              + "Full report: logs/feedcheck.txt")


def main() -> None:
    now = datetime.now(TZ)
    hour = int(os.getenv("START_H") or now.hour)   # hour the run started (before any waiting)
    force = os.getenv("WATCHDOG_FORCE") == "1"
    flag = DATA / "state" / "done" / f"{now:%Y-%m-%d}-watchdog"
    if force or (hour == check_hour() and not flag.exists()):
        check_sent(now)
        if not force:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text(now.isoformat())
        if now.isoweekday() == 7 or os.getenv("FEEDCHECK") == "1":
            check_feeds()
    elif os.getenv("FEEDCHECK") == "1":
        check_feeds()
    else:
        print(f"{hour}h local: the check runs at {check_hour()}h, nothing to do")


if __name__ == "__main__":
    main()
