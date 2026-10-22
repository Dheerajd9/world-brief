"""Settings for World Brief: one place, read from config.yaml (never secrets).

Where config.yaml is looked for: $WB_CONFIG, then /data/config.yaml (Docker), then the repo
root. Missing file = sensible world-news defaults, so the app always runs.

`apply()` copies settings into environment variables the pipeline already understands
(BRIEF_TZ, EMAIL_FROM_NAME, PODCAST, PODCAST_LANGUAGES, ...). An environment variable that is
already set wins, so tests and power users can override anything.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import yaml

APP = Path(__file__).resolve().parent
REPO = APP.parent
FEEDS_DIR = REPO / "feeds"

DEFAULTS: dict = {
    "you": {"name": "", "timezone": "UTC"},
    "email": {"from_name": "World Brief", "send_time": "07:00", "weekly": True,
              "subject_prefix": "🌏 World Brief"},
    "focus": {"countries": [], "cities": []},
    "podcast": {"enabled": True, "hosts": ["Alex", "Maya"], "accent": "en-US",
                "languages": []},
    "telegram": {"enabled": False},
    "alerts": {"breaking": False},
    "feeds_extra": [],
}

# ISO code -> (name, flag, Google News edition). Any code works; these just look nicer.
COUNTRIES = {
    "in": ("India", "🇮🇳", "IN"), "us": ("USA", "🇺🇸", "US"), "gb": ("United Kingdom", "🇬🇧", "GB"),
    "ca": ("Canada", "🇨🇦", "CA"), "au": ("Australia", "🇦🇺", "AU"), "nz": ("New Zealand", "🇳🇿", "NZ"),
    "ie": ("Ireland", "🇮🇪", "IE"), "sg": ("Singapore", "🇸🇬", "SG"), "za": ("South Africa", "🇿🇦", "ZA"),
    "ng": ("Nigeria", "🇳🇬", "NG"), "ke": ("Kenya", "🇰🇪", "KE"), "ph": ("Philippines", "🇵🇭", "PH"),
    "pk": ("Pakistan", "🇵🇰", "PK"), "bd": ("Bangladesh", "🇧🇩", "BD"), "ae": ("UAE", "🇦🇪", "AE"),
    "my": ("Malaysia", "🇲🇾", "MY"), "de": ("Germany", "🇩🇪", "US"), "fr": ("France", "🇫🇷", "US"),
    "jp": ("Japan", "🇯🇵", "US"), "br": ("Brazil", "🇧🇷", "US"), "mx": ("Mexico", "🇲🇽", "US"),
}
SUGGESTED = ["in", "us", "gb", "ca", "au"]          # shown first by the setup wizard

# Optional podcast languages (English is always the main episode).
LANGUAGES = {"te": "Telugu", "hi": "Hindi"}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def path() -> Path:
    for p in (os.getenv("WB_CONFIG"), "/data/config.yaml", REPO / "config.yaml"):
        if p and Path(p).exists():
            return Path(p)
    return REPO / "config.yaml"


def load() -> dict:
    p = path()
    raw = yaml.safe_load(p.read_text()) if p.exists() else {}
    cfg = _merge(DEFAULTS, raw or {})
    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    """Clear messages for the usual mistakes (raise ValueError)."""
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(cfg["you"]["timezone"])
    except Exception:
        raise ValueError(f"config.yaml: unknown timezone {cfg['you']['timezone']!r} "
                         "(examples: Europe/London, America/New_York, Asia/Kolkata)")
    hh, _, mm = str(cfg["email"]["send_time"]).partition(":")
    if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
        raise ValueError("config.yaml: email.send_time must look like 07:00")
    hosts = cfg["podcast"]["hosts"]
    if not (isinstance(hosts, list) and len(hosts) == 2 and all(str(h).strip() for h in hosts)):
        raise ValueError("config.yaml: podcast.hosts needs exactly two names, e.g. [Alex, Maya]")
    for c in cfg["focus"]["countries"]:
        if not (isinstance(c, str) and len(c) == 2 and c.isalpha()):
            raise ValueError(f"config.yaml: focus.countries uses 2-letter codes like in, us, gb (got {c!r})")
    for lang in cfg["podcast"]["languages"]:
        if lang not in LANGUAGES:
            raise ValueError(f"config.yaml: podcast.languages supports {sorted(LANGUAGES)} (got {lang!r})")


def country(code: str) -> tuple[str, str, str]:
    return COUNTRIES.get(code.lower(), (code.upper(), "📍", "US"))


def feeds(cfg: dict) -> dict[str, list[str]]:
    """World pack + a pack per chosen country (or Google News for that country) + city
    searches + the user's own feeds."""
    out = yaml.safe_load((FEEDS_DIR / "world.yaml").read_text())
    for code in cfg["focus"]["countries"]:
        code = code.lower()
        name, _, ed = country(code)
        pack = FEEDS_DIR / f"{code}.yaml"
        if pack.exists():
            for cat, urls in (yaml.safe_load(pack.read_text()) or {}).items():
                out.setdefault(cat, []).extend(urls)
        else:          # any other country: Google News search for it
            out.setdefault(f"{code}_news", []).append(
                f"https://news.google.com/rss/search?q={quote_plus(name)}+when:1d"
                f"&hl=en-{ed}&gl={ed}&ceid={ed}:en")
    countries = cfg["focus"]["countries"]
    for city in cfg["focus"]["cities"]:
        ed = country(countries[0])[2] if countries else "US"
        out.setdefault("cities", []).append(
            f"https://news.google.com/rss/search?q={quote_plus(str(city))}+when:1d"
            f"&hl=en-{ed}&gl={ed}&ceid={ed}:en")
    extra = [u for u in cfg.get("feeds_extra") or [] if str(u).startswith("https://")]
    if extra:
        out["extra"] = extra
    off = set()
    try:                       # feeds the weekly check switched off (dead two Sundays running)
        import json
        data = Path(os.getenv("WB_DATA") or REPO)
        off = set(json.loads((data / "state" / "feeds_disabled.json").read_text()))
    except Exception:
        pass
    out = {k: [u for u in dict.fromkeys(v) if u not in off] for k, v in out.items()}
    return {k: v for k, v in out.items() if v}


def focus_text(cfg: dict) -> dict[str, str]:
    """Placeholders for the prompts: who reads it and which extra sections to write."""
    names = [country(c) for c in cfg["focus"]["countries"]]
    cities = [str(c) for c in cfg["focus"]["cities"]]
    sections = "".join(f"## {flag} {name}\nThe important news for {name}: government and policy, "
                       f"economy and prices, society, anything readers there must know. Only real "
                       f"news from the items.\n\n" for name, flag, _ in names)
    sections += "".join(f"## 🏙️ {city}\nLocal news for {city}: city government, transport, "
                        f"weather events, prices, safety. Omit if nothing meaningful.\n\n"
                        for city in cities)
    where = ", ".join([n for n, _, _ in names] + cities)
    audience = ("Readers: anyone who wants to know what is going on in the whole world"
                + (f", with extra attention to {where}." if where else "."))
    headings = "".join(f"## {flag} {name}\n" for name, flag, _ in names) + \
        "".join(f"## 🏙️ {city}\n" for city in cities)
    return {"AUDIENCE": audience, "FOCUS_SECTIONS": sections, "FOCUS_HEADINGS": headings,
            "FOCUS_PLACES": where or "the whole world",
            "CHAPTERS": ", ".join(["Top stories"] + [n for n, _, _ in names]
                                  + (["Local"] if cities else []) + ["World", "Tech", "Money", "Wrap-up"])}


APPLIED: list[str] = []      # env vars set from config.yaml (tests clear them)


def apply(cfg: dict | None = None) -> dict:
    """Push settings into env vars (existing env wins) and return the config."""
    cfg = cfg or load()

    def put(k, v):
        if v is not None and k not in os.environ:
            os.environ[k] = str(v)
            APPLIED.append(k)
    put("BRIEF_TZ", cfg["you"]["timezone"])
    put("EMAIL_FROM_NAME", cfg["email"]["from_name"])
    put("WB_SEND_TIME", cfg["email"]["send_time"])
    put("WB_WEEKLY", "1" if cfg["email"]["weekly"] else "0")
    put("PODCAST", "1" if cfg["podcast"]["enabled"] else "0")
    put("PODCAST_LANGUAGES", ",".join(cfg["podcast"]["languages"]))
    put("PODCAST_HOST_A", cfg["podcast"]["hosts"][0])
    put("PODCAST_HOST_B", cfg["podcast"]["hosts"][1])
    put("PODCAST_ACCENT", cfg["podcast"]["accent"])
    put("TELEGRAM_ON", "1" if cfg["telegram"]["enabled"] else "0")
    put("WB_ALERTS", "1" if cfg["alerts"]["breaking"] else "0")
    return cfg
