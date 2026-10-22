"""Command line for World Brief (same commands on GitHub Actions, Docker and your computer).

  python -m app run morning|weekly        build and send an edition now
  python -m app run due                   send only what is due now and not sent yet
  python -m app podcast morning|weekly    remake today's podcast from the sent email
  python -m app check keys                test every key, email a report
  python -m app check feeds               test every feed -> logs/feedcheck.txt
  python -m app watchdog                  missing-email check (acts once a day by itself)
  python -m app alerts                    breaking-news check (if enabled in config.yaml)
  python -m app telegram setup            find your Telegram channel after adding the bot
  python -m app setup                     the setup wizard (writes config.yaml / .env)
  python -m app serve                     Docker: run forever, send every day on time
Add --dry-run to build without sending.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))          # the modules import each other by plain name


def _load_env_file() -> None:
    """Read .env (repo root or /data) into the environment, without overriding real env."""
    for p in (os.getenv("WB_ENV_FILE"), "/data/.env", APP.parent / ".env"):
        if p and Path(p).exists():
            for line in Path(p).read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def _run_edition(edition: str) -> int:
    os.environ["EDITION"] = edition
    import digest
    try:
        digest.main()
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"!! {edition} failed: {type(exc).__name__}: {digest.redact(str(exc))[:300]}")
        if os.getenv("DRY_RUN") != "1":
            os.environ["EDITION"] = edition
            import notify_failure  # noqa: F401  (sends the alert on import)
        return 1


def main(argv: list[str]) -> int:
    _load_env_file()
    if "--dry-run" in argv:
        os.environ["DRY_RUN"] = "1"
        argv = [a for a in argv if a != "--dry-run"]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "setup":
        import setup_wizard
        return setup_wizard.main()
    if cmd == "serve":
        import scheduler
        return scheduler.main()
    if cmd == "run":
        what = (rest or ["due"])[0]
        if what == "due":
            from datetime import datetime
            import digest
            edition = digest.due_edition(datetime.now(digest.TZ))
            if not edition:
                print("nothing due right now (or already sent today)")
                return 0
            os.environ.setdefault("WB_SCHEDULED", "1")
            return _run_edition(edition)
        if what not in ("morning", "weekly"):
            print("run what? morning | weekly | due")
            return 2
        return _run_edition(what)
    if cmd == "podcast":
        os.environ["PODCAST_ONLY"] = "1"
        os.environ.setdefault("FORCE", "1")
        return _run_edition((rest or ["morning"])[0])
    if cmd == "check":
        what = (rest or ["keys"])[0]
        if what == "keys":
            import keycheck
            keycheck.main()
            return 0
        if what == "feeds":
            import feedcheck
            feedcheck.main()
            return 0
    if cmd == "watchdog":
        import watchdog
        watchdog.main()
        return 0
    if cmd == "alerts":
        import alerts
        alerts.main()
        return 0
    if cmd == "telegram" and rest[:1] == ["setup"]:
        import tgsetup
        tgsetup.main()
        return 0
    print(f"unknown command: {' '.join(argv)}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
