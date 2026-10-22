"""Test every news feed in use (`python -m app check feeds`): downloads each one the same way the
brief does and prints which are dead, empty or stale, so bad feeds can be removed.
Sends nothing. Prints a table and writes it to the GitHub step summary.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).parent
DATA = Path(os.getenv("WB_DATA") or Path(__file__).resolve().parent.parent)   # state, briefs, logs (Docker: /data)
UA = {"User-Agent": "world-brief/1.0 (personal news digest)"}


def download(url: str):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        return r.content
    except Exception as exc:
        return exc


def check(feeds: dict[str, list[str]], get=download, hours: int = 26) -> list[dict]:
    """One row per feed: status ok / empty / stale / dead, items, fresh items (last `hours`)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    urls = list(dict.fromkeys(u for us in feeds.values() for u in us))
    with ThreadPoolExecutor(max_workers=10) as pool:
        got = dict(zip(urls, pool.map(get, urls)))
    rows = []
    for cat, us in feeds.items():
        for u in us:
            g = got[u]
            if isinstance(g, Exception) or g is None:
                rows.append({"cat": cat, "url": u, "status": "dead", "items": 0, "fresh": 0,
                             "why": type(g).__name__ + (f" {g.response.status_code}" if getattr(g, "response", None) is not None else "")})
                continue
            entries = feedparser.parse(g).entries
            fresh = 0
            for e in entries:
                t = e.get("published_parsed") or e.get("updated_parsed")
                if not t or datetime(*t[:6], tzinfo=timezone.utc) >= cutoff:
                    fresh += 1
            status = "empty" if not entries else ("stale" if not fresh else "ok")
            rows.append({"cat": cat, "url": u, "status": status, "items": len(entries), "fresh": fresh, "why": ""})
    return rows


def report(rows: list[dict]) -> str:
    bad = [r for r in rows if r["status"] != "ok"]
    lines = [f"Feeds: {len(rows)} · ok {len(rows) - len(bad)} · problems {len(bad)} · "
             f"fresh items {sum(r['fresh'] for r in rows)}", ""]
    for r in sorted(bad, key=lambda r: r["status"]):
        lines.append(f"{r['status'].upper():6} {r['cat']:24} {r['items']:4} {r['why']:18} {r['url']}")
    lines.append("")
    for r in rows:
        if r["status"] == "ok":
            lines.append(f"ok     {r['cat']:24} {r['fresh']:4}/{r['items']:<4} {r['url']}")
    return "\n".join(lines)


def main() -> None:
    import config
    out = report(check(config.feeds(config.load())))
    print(out)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("```\n" + out + "\n```\n")


if __name__ == "__main__":
    main()
