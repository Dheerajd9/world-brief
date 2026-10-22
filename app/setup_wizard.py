"""Setup wizard: a few questions -> config.yaml (+ .env for Docker / your computer).

Run:  python setup.py          (GitHub Codespace or your computer)
      docker compose run --rm world-brief setup
Secrets (keys, passwords, emails) never go into config.yaml.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import config

ACCENTS = ["en-US", "en-GB", "en-IN", "en-AU", "en-CA"]


def _guess_tz() -> str:
    for cand in (os.getenv("TZ"), _read("/etc/timezone")):
        if cand and _valid_tz(cand.strip()):
            return cand.strip()
    try:
        link = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in link and _valid_tz(link.split("zoneinfo/", 1)[1]):
            return link.split("zoneinfo/", 1)[1]
    except Exception:
        pass
    return "UTC"


def _read(p: str) -> str:
    try:
        return Path(p).read_text()
    except Exception:
        return ""


def _valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


class Asker:
    def __init__(self, ask=input, say=print):
        self.ask, self.say = ask, say

    def text(self, q: str, default: str = "") -> str:
        a = self.ask(f"{q}" + (f" [{default}]" if default else "") + ": ").strip()
        return a or default

    def yes(self, q: str, default: bool) -> bool:
        a = self.ask(f"{q} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        return default if not a else a.startswith("y")

    def codes(self, q: str, allowed=None) -> list[str]:
        a = self.ask(q + ": ").strip()
        out = [c.strip().lower() for c in a.replace(" ", ",").split(",") if c.strip()]
        bad = [c for c in out if (allowed and c not in allowed) or (not allowed and len(c) != 2)]
        if bad:
            self.say(f"  ignoring: {', '.join(bad)}")
        return [c for c in out if c not in bad]


def build(a: Asker) -> tuple[dict, dict]:
    """Ask everything; return (config, secrets)."""
    a.say("\n🌏 World Brief setup — about 2 minutes. Press Enter to accept [defaults].\n")
    cfg = {"you": {}, "email": {}, "focus": {}, "podcast": {}, "telegram": {}, "alerts": {}}
    cfg["you"]["name"] = a.text("Your first name (shown nowhere public)", "")
    tz = a.text("Your time zone (e.g. Europe/London, America/New_York, Asia/Kolkata)", _guess_tz())
    while not _valid_tz(tz):
        tz = a.text("  not a known time zone, try again", "UTC")
    cfg["you"]["timezone"] = tz
    cfg["email"]["send_time"] = a.text("What time should the email arrive? (24h)", "07:00")
    cfg["email"]["from_name"] = a.text("Sender name shown in the inbox", "World Brief")

    a.say("\nThe brief always covers the WHOLE WORLD. You can also add extra focus on some "
          "countries (their own section).\nSuggestions: "
          + ", ".join(f"{c} = {config.country(c)[0]}" for c in config.SUGGESTED)
          + " (any 2-letter country code works).")
    cfg["focus"]["countries"] = a.codes("Extra countries (comma-separated, Enter = none)")
    cities = a.text("Extra cities to follow (comma-separated, Enter = none)", "")
    cfg["focus"]["cities"] = [c.strip() for c in cities.split(",") if c.strip()]

    pod = a.yes("\nInclude a two-host podcast (15-30 min) in the email?", True)
    cfg["podcast"]["enabled"] = pod
    if pod:
        hosts = a.text("Two host names", "Alex, Maya")
        names = [h.strip() for h in hosts.split(",") if h.strip()][:2]
        cfg["podcast"]["hosts"] = names if len(names) == 2 else ["Alex", "Maya"]
        acc = a.text(f"Voice accent ({' / '.join(ACCENTS)})", "en-US")
        cfg["podcast"]["accent"] = acc if acc in ACCENTS else "en-US"
        a.say("English is the main podcast. Optional extra languages: "
              + ", ".join(f"{k} = {v}" for k, v in config.LANGUAGES.items())
              + " (more can be added later).")
        cfg["podcast"]["languages"] = a.codes("Extra podcast languages (Enter = none)",
                                              allowed=set(config.LANGUAGES))
    cfg["email"]["weekly"] = a.yes("Also send a Sunday weekly deep-dive?", True)
    cfg["telegram"]["enabled"] = a.yes("Also post it to a Telegram channel?", False)
    cfg["alerts"]["breaking"] = a.yes("Breaking-news alert emails (only for truly big news)?", False)

    a.say("\nNow the free keys (they are NOT saved in config.yaml).")
    a.say("  Gemini key: https://aistudio.google.com/apikey  ·  Gmail app password: "
          "https://myaccount.google.com/apppasswords (2-step verification must be on)")
    sec = {"GEMINI_API_KEY": a.text("Gemini API key"),
           "GMAIL_USER": a.text("Gmail address that sends the email"),
           "GMAIL_APP_PASSWORD": a.text("Gmail app password (16 letters)").replace(" ", "")}
    sec["TO_EMAIL"] = a.text("Your email (receives the brief + alerts)", sec["GMAIL_USER"])
    sec["EXTRA_EMAILS"] = a.text("Other people to receive it (comma-separated, optional)", "")
    if cfg["telegram"]["enabled"]:
        sec["TELEGRAM_BOT_TOKEN"] = a.text("Telegram bot token (from @BotFather)")
    sec["MISTRAL_API_KEY"] = a.text("Optional backup AI: Mistral key (Enter to skip)", "")
    return cfg, {k: v for k, v in sec.items() if v}


def config_path() -> Path:
    if os.getenv("WB_CONFIG"):
        return Path(os.environ["WB_CONFIG"])
    if os.getenv("WB_DATA"):
        return Path(os.environ["WB_DATA"]) / "config.yaml"
    return config.REPO / "config.yaml"


def write(cfg: dict, secrets: dict, mode: str, say=print) -> None:
    full = config._merge(config.DEFAULTS, cfg)
    config.validate(full)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# World Brief settings (made by the setup wizard; edit freely).\n"
                    "# Every option: config.example.yaml\n"
                    + yaml.safe_dump(full, sort_keys=False, allow_unicode=True))
    say(f"\n✅ Saved {path}")
    if mode == "github":
        say("\nAdd these as repository secrets: Settings -> Secrets and variables -> Actions "
            "-> New repository secret:")
        for k in secrets:
            say(f"  {k}")
        if shutil.which("gh") and secrets:
            say("\n(GitHub CLI found: you can also run, from this folder:)")
            for k in secrets:
                say(f"  gh secret set {k}")
        say("\nThen commit config.yaml, and run: Actions -> World Brief -> Run workflow -> keycheck.")
    else:
        env = path.parent / ".env"
        env.write_text("".join(f"{k}={v}\n" for k, v in secrets.items()))
        try:
            env.chmod(0o600)
        except Exception:
            pass
        say(f"✅ Saved your keys to {env} (only on this machine; never commit it).")
        say("Test now:  python -m app check keys   (Docker: docker compose run --rm world-brief check keys)")


def main(ask=input, say=print) -> int:
    a = Asker(ask, say)
    try:
        cfg, secrets = build(a)
    except (KeyboardInterrupt, EOFError):
        say("\nSetup cancelled; nothing saved.")
        return 1
    on_github = bool(os.getenv("CODESPACES") or os.getenv("GITHUB_ACTIONS"))
    mode = "github" if (on_github or a.yes("\nWill GitHub run it for you (template mode)? "
                                           "No = Docker / this computer", not os.getenv("WB_DATA"))) \
        else "local"
    write(cfg, secrets, mode, say)
    return 0


if __name__ == "__main__":
    sys.exit(main())
