"""
Optional breaking-news alerts by email (config.yaml alerts.breaking). Runs every 2 hours; usually sends nothing.

1. Fetch a few fast feeds (watchlist.yaml) for the last few hours.
2. Candidates = headlines matching your watchlist keywords, or stories many outlets
   ran at once (wide coverage = something big is happening).
3. A free LLM (GitHub Models first, Gemini backup) scores each 1-10 for *this* reader.
4. Score >= min_score -> an email (never Telegram: the channel gets only the daily message).
State (what was already checked/sent) lives in state/alerts_seen.json, kept between
runs by the Actions cache, so you never get the same alert twice.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

import digest

ROOT = Path(__file__).parent
DATA = Path(os.getenv("WB_DATA") or Path(__file__).resolve().parent.parent)   # state, briefs, logs (Docker: /data)
STATE = DATA / "state" / "alerts_seen.json"


def load_state() -> dict:
    try:
        s = json.loads(STATE.read_text())
    except Exception:
        s = {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    s["seen"] = {k: v for k, v in s.get("seen", {}).items() if v >= cutoff}
    s.setdefault("sent_per_day", {})
    return s


def keyword_regex(cfg: dict) -> tuple[re.Pattern, re.Pattern]:
    words = [w for group in cfg["keywords"].values() for w in group]
    # ALL-CAPS acronyms (RBI, OPT, GST) match case-sensitively so "opt out" doesn't fire.
    acr = [re.escape(w) for w in words if w.isupper()]
    rest = [re.escape(w) for w in words if not w.isupper()]
    return (re.compile(r"\b(" + "|".join(acr) + r")\b") if acr else re.compile(r"$^"),
            re.compile(r"\b(" + "|".join(rest) + r")\b", re.I) if rest else re.compile(r"$^"))


def candidates(cfg: dict, state: dict) -> list[dict]:
    digest.LOOKBACK_HOURS = cfg["lookback_hours"]
    items = digest.dedupe(digest.fetch_items({"alerts": cfg["feeds"]}), state["seen"])
    acr, rest = keyword_regex(cfg)
    out = []
    for it in items:
        text = f"{it['title']} {it['summary']}"
        if acr.search(text) or rest.search(text) or it["coverage"] >= cfg["wide_coverage"]:
            out.append(it)
    for n, it in enumerate(out[:40], 1):
        it["id"] = f"A{n}"
    return out[:40], items


def score(cands: list[dict]) -> list[dict]:
    system = (ROOT / "prompts" / "alert_prompt.md").read_text()
    for key, val in digest.FOCUS.items():
        system = system.replace("{" + key + "}", val)
    payload = [{"id": c["id"], "source": c["source"], "coverage": c["coverage"],
                "title": c["title"]} for c in cands]
    reply = digest.ask(system, json.dumps(payload, ensure_ascii=False), prefer="backup")
    if not reply:
        return []
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
        alerts = data.get("alerts", []) if isinstance(data, dict) else []
        return alerts if isinstance(alerts, list) else []
    except json.JSONDecodeError:
        return []


def deliver(alerts: list[dict]) -> None:
    for a in alerts:   # only real article links from our feeds, never one the AI made up
        if str(a.get("link", "")) not in digest.KNOWN_LINKS:
            a["link"] = ""
    # Email only: the Telegram channel carries just the one daily message (news + podcast).
    md = "\n\n".join(f"### 🚨 {a['headline']}\n{a.get('why', '')}"
                     + (f"  \n[{a.get('source', 'Source')}]({a['link']})" if a["link"] else "")
                     for a in alerts)
    digest.send_email(f"🚨 Breaking: {alerts[0]['headline']}", md)


def main() -> None:
    if os.getenv("WB_ALERTS", "0") != "1":
        print("breaking alerts are off (config.yaml: alerts: {breaking: true} to turn on)")
        return
    cfg = yaml.safe_load((ROOT / "watchlist.yaml").read_text())
    state = load_state()
    today = datetime.now(digest.TZ).strftime("%Y-%m-%d")
    sent_today = state["sent_per_day"].get(today, 0)

    cands, all_items = candidates(cfg, state)
    print(f"{len(all_items)} fresh items, {len(cands)} candidates, {sent_today} alerts sent today")
    stamp = datetime.now(timezone.utc).isoformat()
    for it in all_items:                    # everything checked is remembered, sent or not
        state["seen"][digest.key_of(it)] = stamp

    picked = []
    if cands and sent_today < cfg["max_alerts_per_day"] and os.getenv("NO_LLM") != "1":
        by_id = {c["id"]: c for c in cands}
        scored = []
        for s in score(cands):             # the AI's JSON may be messy: keep only sane rows
            try:
                if isinstance(s, dict) and str(s.get("headline", "")).strip():
                    scored.append({**s, "score": float(s.get("score", 0))})
            except (TypeError, ValueError):
                continue
        for s in sorted(scored, key=lambda s: -s["score"]):
            c = by_id.get(s.get("id"))
            if c and s["score"] >= cfg["min_score"]:
                picked.append({**s, "link": c["link"], "source": c["source"]})
        picked = picked[:max(0, cfg["max_alerts_per_day"] - sent_today)][:3]

    if picked:
        print("  alerts:", [f"{p['score']} {p['headline']}" for p in picked])
        if os.getenv("DRY_RUN") != "1":
            deliver(picked)
            state["sent_per_day"] = {today: sent_today + len(picked)}
    else:
        print("  nothing alert-worthy")

    if os.getenv("DRY_RUN") != "1":
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(state, indent=0))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"! alerts failed: {type(exc).__name__}: {digest.redact(str(exc))[:200]}",
              file=sys.stderr)
