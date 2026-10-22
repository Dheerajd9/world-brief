"""Optional short weather line for the podcasts, from the free
Open-Meteo API (no key, no sign-up). Never raises: returns "" if anything fails.

  WEATHER_PLACES   "Name:lat:lon;Name:lat:lon" (no default; set it to switch places on)
  WEATHER          off by default; set to 1 to switch the forecast line back on
"""

from __future__ import annotations

import os

import requests

DEFAULT_PLACES = ""
URL = "https://api.open-meteo.com/v1/forecast"

CODES = {0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy", 45: "fog", 48: "fog",
         51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
         65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
         75: "heavy snow", 77: "snow", 80: "rain showers", 81: "rain showers",
         82: "heavy rain showers", 85: "snow showers", 86: "snow showers", 95: "thunderstorm",
         96: "thunderstorm with hail", 99: "thunderstorm with hail"}

_CACHE: dict[str, str] = {}


_FETCHED: dict[tuple, dict] = {}


def fetch(lat: float, lon: float) -> dict:
    """Open-Meteo forecast (current + 2 days, local time zone). Cached per run: the email's
    weather line and the podcasts share one request."""
    if (lat, lon) in _FETCHED:
        return _FETCHED[(lat, lon)]
    r = requests.get(URL, timeout=10, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 2,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"})
    r.raise_for_status()
    _FETCHED[(lat, lon)] = r.json()
    return _FETCHED[(lat, lon)]


def _place(name: str, d: dict) -> str:
    cur, day = d.get("current", {}), d.get("daily", {})

    def dly(key, i):
        vals = day.get(key) or []
        return vals[i] if len(vals) > i and vals[i] is not None else None

    parts = []
    if cur.get("temperature_2m") is not None:
        parts.append(f"now {round(cur['temperature_2m'])}°C, {CODES.get(cur.get('weather_code'), 'mixed')}")
    for i, label in ((0, "today"), (1, "tomorrow")):
        hi, lo, rain = dly("temperature_2m_max", i), dly("temperature_2m_min", i), \
            dly("precipitation_probability_max", i)
        if hi is None:
            continue
        txt = f"{label} {round(lo)}–{round(hi)}°C, {CODES.get(dly('weather_code', i), 'mixed')}"
        if rain is not None:
            txt += f", rain chance {round(rain)}%"
        parts.append(txt)
    return f"{name}: " + "; ".join(parts) if parts else ""


def line() -> str:
    """e.g. 'Paris: now 18°C, light rain; today 12–19°C, ... ' (local days)."""
    if os.getenv("WEATHER", "0") != "1":
        return ""
    if "line" in _CACHE:
        return _CACHE["line"]
    out = []
    for spec in [s for s in (os.getenv("WEATHER_PLACES") or DEFAULT_PLACES).split(";") if s]:
        try:
            name, lat, lon = spec.split(":")
            txt = _place(name.strip(), fetch(float(lat), float(lon)))
            if txt:
                out.append(txt)
        except Exception as exc:
            print(f"  ! weather for one place skipped: {type(exc).__name__}")
    _CACHE["line"] = " | ".join(out)
    return _CACHE["line"]
