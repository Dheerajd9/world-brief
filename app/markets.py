"""
Exact numbers: market snapshot, gold & silver, weather, from free keyless data sources.
The AI never writes these numbers; they come straight from the data, so they're always right.

Markets: Yahoo Finance chart endpoint (unofficial, free), Stooq CSV fallback,
         Frankfurter (ECB) last-resort fallback for USD/INR.
Gold/silver India: IBJA (India Bullion & Jewellers Association) benchmark rates.
Weather: Open-Meteo (free, no key).
Anything that fails is left out; it never breaks the email.
"""

from __future__ import annotations

import os

import csv
import io
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

UA = {"User-Agent": "Mozilla/5.0 (world-brief news digest)"}
OZ = 31.1035  # grams in one troy ounce

# label, yahoo, stooq, kind   (kind: index | fx | usd | usd0 | yield)
# World table (everyone). Country rows are added for the countries in config.yaml focus.
INDICES = [
    ("🇺🇸 S&P 500", "^GSPC", "^spx", "index"),
    ("🇺🇸 Nasdaq Composite", "^IXIC", "^ndq", "index"),
    ("🇪🇺 Euro Stoxx 50", "^STOXX50E", None, "index"),
    ("🇯🇵 Nikkei 225", "^N225", "^nkx", "index"),
    ("💶 EUR/USD", "EURUSD=X", "eurusd", "fx4"),
]
COUNTRY_ROWS = {
    "in": [("🇮🇳 Nifty 50", "^NSEI", None, "index"), ("🇮🇳 Sensex", "^BSESN", None, "index"),
           ("💵 USD/INR", "INR=X", "usdinr", "fx")],
    "us": [("🇺🇸 Dow Jones", "^DJI", "^dji", "index")],
    "gb": [("🇬🇧 FTSE 100", "^FTSE", "^ukx", "index"), ("💷 GBP/USD", "GBPUSD=X", "gbpusd", "fx4")],
    "ca": [("🇨🇦 S&P/TSX", "^GSPTSE", None, "index"), ("🇨🇦 USD/CAD", "CAD=X", "usdcad", "fx4")],
    "au": [("🇦🇺 ASX 200", "^AXJO", None, "index"), ("🇦🇺 AUD/USD", "AUDUSD=X", "audusd", "fx4")],
    "jp": [("💴 USD/JPY", "JPY=X", "usdjpy", "fx4")],
    "de": [("🇩🇪 DAX", "^GDAXI", "^dax", "index")],
    "fr": [("🇫🇷 CAC 40", "^FCHI", "^cac", "index")],
    "sg": [("🇸🇬 Straits Times", "^STI", None, "index")],
    "br": [("🇧🇷 Bovespa", "^BVSP", None, "index")],
}


def focus_codes() -> list[str]:
    try:
        import config
        return [c.lower() for c in config.load()["focus"]["countries"]]
    except Exception:
        return []


TAIL = [
    ("🛢️ Brent crude ($/bbl)", "BZ=F", "cb.f", "usd"),
    ("₿ Bitcoin", "BTC-USD", "btcusd", "usd0"),
    ("🇺🇸 US 10-year Treasury yield", "^TNX", None, "yield"),
]
# Given to the AI only; it mentions them when something meaningful happened.
EXTRA = [
    ("Dow Jones", "^DJI", "^dji", "index"), ("FTSE 100", "^FTSE", "^ukx", "index"),
    ("DAX (Germany)", "^GDAXI", "^dax", "index"), ("Shanghai (China)", "000001.SS", None, "index"),
    ("Hang Seng (Hong Kong)", "^HSI", None, "index"), ("WTI oil ($/bbl)", "CL=F", "cl.f", "usd"),
    ("US VIX (fear index)", "^VIX", None, "index2"), ("US Dollar Index (DXY)", "DX-Y.NYB", None, "index2"),
    ("GBP/USD", "GBPUSD=X", "gbpusd", "fx4"), ("USD/JPY", "JPY=X", "usdjpy", "fx4"),
    ("USD/CNY", "CNY=X", "usdcny", "fx4"), ("USD/INR", "INR=X", "usdinr", "fx"),
    ("US natural gas", "NG=F", "ng.f", "usd"), ("Ethereum", "ETH-USD", "ethusd", "usd0"),
]

CITIES: list = []        # weather rows are off in the public edition
WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy", 45: "fog", 48: "fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
       65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "showers",
       81: "showers", 82: "heavy showers", 95: "thunderstorms", 96: "thunderstorms with hail",
       99: "severe thunderstorms"}


# ---------------------------------------------------------------- price data
def _yahoo(symbol: str) -> tuple[list[float], float | None]:
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                     params={"range": "1mo", "interval": "1d"}, headers=UA, timeout=15)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    return closes, res.get("meta", {}).get("regularMarketTime")


def _stooq(symbol: str) -> tuple[list[float], float | None]:
    r = requests.get("https://stooq.com/q/d/l/", params={"s": symbol, "i": "d"},
                     headers=UA, timeout=15)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    return [float(row["Close"]) for row in rows[-25:] if row.get("Close")], None


def _frankfurter_usdinr() -> tuple[list[float], float | None]:
    end = datetime.utcnow().date()
    r = requests.get(f"https://api.frankfurter.app/{end - timedelta(days=14)}..{end}",
                     params={"from": "USD", "to": "INR"}, timeout=15)
    r.raise_for_status()
    rates = r.json()["rates"]
    return [rates[d]["INR"] for d in sorted(rates)], None


_CACHE: dict[str, tuple[list[float], float | None]] = {}


def series(yahoo: str, stooq: str | None) -> tuple[list[float], float | None]:
    """(daily closes oldest->newest, unix time of latest quote or None)."""
    if yahoo in _CACHE:
        return _CACHE[yahoo]
    out: tuple[list[float], float | None] = ([], None)
    for fn, sym in ((_yahoo, yahoo), (_stooq, stooq)):
        if not sym:
            continue
        try:
            closes, t = fn(sym)
            if len(closes) >= 2:
                out = (closes, t)
                break
        except Exception:
            pass
    if not out[0] and yahoo == "INR=X":
        try:
            out = _frankfurter_usdinr()
        except Exception:
            pass
    _CACHE[yahoo] = out
    return out


def closes_for(yahoo: str, stooq: str | None) -> list[float]:
    return series(yahoo, stooq)[0]


def status_of(t: float | None, kind: str) -> str:
    if t is None:
        return "PREVIOUS CLOSE"
    age = time.time() - t
    if age < 35 * 60:
        return "LIVE (delayed)" if kind == "usd0" else "DELAYED"
    if kind == "usd0":
        return "LATEST AVAILABLE"
    if age > 4 * 86400:
        return "STALE"
    # A weekend or holiday gap means the exchange is closed right now.
    return "MARKET CLOSED" if datetime.now(timezone.utc).weekday() >= 5 else "PREVIOUS CLOSE"


# ---------------------------------------------------------------- formatting
def inr(v: float, decimals: int = 0) -> str:
    """Indian digit grouping: 464786.5 -> '₹4,64,787'."""
    whole = int(v) if decimals else int(round(v))
    n = str(whole)
    head, tail = n[:-3], n[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    s = "₹" + ",".join(([head] if head else []) + groups + [tail])
    if decimals:
        s += f"{v - whole:.{decimals}f}"[1:]
    return s


def fmt_value(v: float, kind: str) -> str:
    return {"fx": f"₹{v:,.2f}", "fx4": f"{v:,.4f}", "usd": f"${v:,.2f}", "usd0": f"${v:,.0f}",
            "yield": f"{v:.2f}%", "index2": f"{v:,.2f}"}.get(kind, f"{v:,.0f}")


def fmt_change(now: float, then: float, kind: str) -> str:
    if kind == "yield":
        d = now - then
        arrow = "▲" if d > 0.004 else "▼" if d < -0.004 else "■"
        return f"{arrow} {d:+.2f} pts"
    pct = (now - then) / then * 100
    arrow = "▲" if pct > 0.005 else "▼" if pct < -0.005 else "■"
    return f"{arrow} {pct:+.2f}%"


def _row(label: str, ysym: str, ssym: str | None, kind: str, weekly: bool) -> dict | None:
    closes, t = series(ysym, ssym)
    if len(closes) < 2:
        return None
    back = (8 if kind == "usd0" else 6) if weekly else 2
    then = closes[-back] if len(closes) >= back else closes[0]
    return {"label": label, "value": fmt_value(closes[-1], kind),
            "change": fmt_change(closes[-1], then, kind),
            "status": "1-WEEK CHANGE" if weekly else status_of(t, kind)}


# ---------------------------------------------------------------- India bullion
def ibja_rates() -> dict[str, float]:
    """IBJA benchmark: gold per gram (999, 916) and silver per kg if shown.
    Rates are without 3% GST and making charges."""
    r = requests.get("https://ibjarates.com/", headers=UA, timeout=20)
    r.raise_for_status()
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    out = {}
    for purity in ("999", "916"):
        m = re.search(purity + r" ?Purity\D{0,40}?([\d,]{4,8})\s*\(\s*1\s*Gram", text)
        if m:
            v = float(m.group(1).replace(",", ""))
            if 3000 < v < 100000:
                out[purity] = v
    m = re.search(r"Silver\D{0,60}?([\d,]{5,9})\s*\(\s*1\s*K", text, re.I)
    if m:
        v = float(m.group(1).replace(",", ""))
        if 30000 < v < 2000000:
            out["silver_kg"] = v
    return out


_IBJA: dict | None = None


def ibja() -> dict:
    global _IBJA
    if _IBJA is None:
        try:
            _IBJA = ibja_rates()
        except Exception:
            _IBJA = {}
    return _IBJA


def metal_rows(weekly: bool) -> list[dict]:
    """Gold & silver rows, all derived from ONE set of numbers so they stay consistent:
    USD/gram = USD/oz / 31.1035, rupee conversions use the same USD/INR as the table."""
    rows = []
    gold, gt = series("GC=F", "xauusd")
    silver, st = series("SI=F", "xagusd")
    india = "in" in focus_codes()
    fx = closes_for("INR=X", "usdinr") if india else []
    rate = ibja() if india else {}
    back = 6 if weekly else 2

    def chg(c):
        then = c[-back] if len(c) >= back else c[0]
        return fmt_change(c[-1], then, "usd")

    if rate.get("999"):
        g24 = rate["999"]
        rows += [
            {"label": "🪙 Gold 24K India (₹/gram)", "value": inr(g24), "change": "—",
             "status": "LATEST AVAILABLE (IBJA)"},
            {"label": "🪙 Gold 24K India (₹/10 grams)", "value": inr(g24 * 10), "change": "—",
             "status": "LATEST AVAILABLE (IBJA)"},
            {"label": "🪙 Gold 24K India (₹/troy ounce)", "value": inr(g24 * OZ), "change": "—",
             "status": "LATEST AVAILABLE (IBJA)"},
        ]
        if rate.get("916"):
            rows.append({"label": "🪙 Gold 22K India (₹/gram)", "value": inr(rate["916"]),
                         "change": "—", "status": "LATEST AVAILABLE (IBJA)"})
    elif gold and fx:
        g = gold[-1] * fx[-1] / OZ
        rows.append({"label": "🪙 Gold India (world price in ₹/gram)", "value": inr(g),
                     "change": chg(gold), "status": "CONVERTED (before duty & GST)"})
    if gold:
        stat = "1-WEEK CHANGE" if weekly else status_of(gt, "usd")
        rows += [
            {"label": "🪙 Gold world ($/gram)", "value": f"${gold[-1] / OZ:,.2f}",
             "change": chg(gold), "status": stat},
            {"label": "🪙 Gold world ($/troy ounce)", "value": f"${gold[-1]:,.2f}",
             "change": chg(gold), "status": stat},
        ]
    if silver:
        kg = rate.get("silver_kg")
        if kg:
            rows.append({"label": "🥈 Silver India (₹/kg)", "value": inr(kg), "change": "—",
                         "status": "LATEST AVAILABLE (IBJA)"})
        elif fx:
            rows.append({"label": "🥈 Silver India (world price in ₹/kg)",
                         "value": inr(silver[-1] / OZ * 1000 * fx[-1]), "change": chg(silver),
                         "status": "CONVERTED (before duty & GST)"})
        rows.append({"label": "🥈 Silver world ($/ounce)", "value": f"${silver[-1]:,.2f}",
                     "change": chg(silver),
                     "status": "1-WEEK CHANGE" if weekly else status_of(st, "usd")})
    return rows


# ---------------------------------------------------------------- weather
def weather_rows() -> list[dict]:
    """One line per city for the email's money section (data from weather.py, shared with the
    podcasts, so Open-Meteo is asked only once per city per run)."""
    import weather
    if os.getenv("WEATHER", "0") != "1":      # forecast switched off (on request)
        return []
    rows = []
    for city, lat, lon, tz, unit in CITIES:
        try:
            d = weather.fetch(lat, lon)["daily"]
            i = 1 if datetime.now(ZoneInfo(tz)).hour >= 15 else 0   # late in their day -> tomorrow
            day = datetime.fromisoformat(d["time"][i]).strftime("%a %d %b")
            rows.append({"city": city, "day": day, "text": (
                f"{WMO.get(d['weather_code'][i], 'mixed')}, "
                f"{d['temperature_2m_max'][i]:.0f}°/{d['temperature_2m_min'][i]:.0f}°{unit}, "
                f"rain {d['precipitation_probability_max'][i] or 0:.0f}%")})
        except Exception:
            pass
    return rows


# ---------------------------------------------------------------- the box
def numbers_box(weekly: bool = False) -> tuple[str, str]:
    """ONE compact money dashboard (markdown) + plain text for the AI and podcast."""
    country = [row for c in focus_codes() for row in COUNTRY_ROWS.get(c, [])]
    rows = [r for r in (_row(l, y, s, k, weekly) for l, y, s, k in INDICES + country) if r]
    try:
        rows += metal_rows(weekly)
    except Exception:
        pass
    rows += [r for r in (_row(l, y, s, k, weekly) for l, y, s, k in TAIL) if r]
    extra = [r for r in (_row(l, y, s, k, weekly) for l, y, s, k in EXTRA) if r]
    weather = weather_rows()
    if not (rows or weather):
        return "", ""

    stamp = datetime.now(ZoneInfo(os.getenv("BRIEF_TZ") or "UTC")).strftime("%d %b %Y, %I:%M %p %Z")
    head = "1-week change" if weekly else "Change"
    md = ["## 📊 Money & markets", "", f"| Asset | Latest | {head} | Status |",
          "|---|---:|---:|---|"]
    md += [f"| {r['label']} | {r['value']} | {r['change']} | {r['status']} |" for r in rows]
    notes = [f"Data as of {stamp}."]
    if "in" in focus_codes():
        fx = closes_for("INR=X", "usdinr")
        if fx:
            notes.append(f"Rupee conversions use ₹{fx[-1]:,.2f} per $.")
        notes.append("India gold/silver = IBJA benchmark rates, without 3% GST and making "
                     "charges; world prices are international spot/futures.")
    md += ["", "_" + " ".join(notes) + "_"]
    if weather:
        md += ["", "Weather: " + " · ".join(f"{w['city']} ({w['day']}) {w['text']}" for w in weather)]
    md.append("")

    plain = [f"{r['label']} {r['value']} ({r['change']}, {r['status']})" for r in rows + extra]
    plain += [f"{w['city']} weather {w['day']}: {w['text']}" for w in weather]
    plain.append(f"MARKET_DATA_TIMESTAMP {stamp}")
    return "\n".join(md), "; ".join(plain)
