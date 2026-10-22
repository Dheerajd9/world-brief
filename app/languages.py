"""
Optional extra podcast languages (Telugu, Hindi): the same English episode translated, so
ONE email can offer the news in more than one language.

  PODCAST_LANGUAGES   comma list from config.yaml podcast.languages (default none: English only)
  LANG_EDITIONS       editions that get them (default "morning,weekly")
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

import digest
import podfeed

ROOT = Path(__file__).parent
DATA = Path(os.getenv("WB_DATA") or Path(__file__).resolve().parent.parent)   # state, briefs, logs (Docker: /data)

LANGS = {
    "te": {"name": "telugu", "label": "🟠 Telugu", "show": "ఈ రోజు వార్తలు",
           "hosts": "Ravi & Lakshmi", "archive": DATA / "briefs" / "telugu"},
    "hi": {"name": "hindi", "label": "🟢 Hindi", "show": "आज की खबरें",
           "hosts": "Arjun & Meera", "archive": DATA / "briefs" / "hindi"},
}

LENGTHS = {
    "MORNING": ("About 1,900 to 4,000 words (15 to 30 minutes spoken, up to 30 on a big news day): the same full coverage as "
                "the English Full podcast. Cover every story in the brief that matters, with real "
                "explanation; shorter only on a genuinely quiet news day. Do not stop early."),
    "EVENING": ("About 500 to 1,500 words (4 to 10 minutes spoken): only what changed since the "
                "morning, biggest change first. Shorter if little changed."),
    "WEEKLY": ("About 1,900 to 4,000 words (15 to 30 minutes spoken): the week's big patterns, "
               "same coverage as the English weekly podcast. Do not stop early."),
}


def _redact(text: str) -> str:
    return digest.redact(text)


def wanted(edition: str) -> list[str]:
    if edition not in os.getenv("LANG_EDITIONS", "morning,evening,weekly").split(","):
        return []
    return [c.strip() for c in os.getenv("PODCAST_LANGUAGES", "").split(",")
            if c.strip() in LANGS]


def make_episodes(final_md: str, date_str: str, now: datetime, out_dir: Path,
                  report_type: str, langs: list[str], dry: bool,
                  base_script: str = "", over_time=None) -> list[dict]:
    """Build (and upload) one podcast per language. Never raises."""
    from podcast import make_podcast, latest_previous_script
    news = digest.strip_links(final_md.replace("{{LISTEN}}", ""))
    news = re.sub(r"(?ms)^##\s*🎧.*?(?=^## |\Z)", "", news)      # the Listen block is not news
    episodes = []
    for code in langs:
        info = LANGS[code]
        if over_time and over_time(f"{info['name'].title()} podcast"):
            continue
        sfx = "" if report_type == "MORNING" else f"-{report_type.lower()}"
        mp3 = None
        for attempt in (1, 2):           # AI busy? wait a bit and try once more
            try:
                mp3 = make_podcast(news, date_str, out_dir,
                                   lambda s, u: digest.ask(s, u, prefer="gemini"),
                                   length=LENGTHS.get(report_type, LENGTHS["MORNING"]),
                                   show=info["show"], lang=code,
                                   report_type=report_type,
                                   out_name=f"{info['name']}_podcast.mp3",
                                   previous_script=latest_previous_script(info["archive"], "podcast", 3000),
                                   base_script=base_script)
            except Exception as exc:
                print(f"  ! {info['name']} podcast failed: {type(exc).__name__}: "
                      f"{_redact(str(exc))[:200]}", file=sys.stderr)
            if mp3:
                break
            if attempt == 1:
                if over_time and over_time(f"{info['name'].title()} retry"):
                    break
                print(f"  {info['name']} script failed; retrying in 90s")
                time.sleep(90)
        if not mp3:
            continue
        url = None
        if podfeed.configured() and not dry:
            for attempt in (1, 2):
                try:
                    url = podfeed.upload_asset(mp3, f"{now:%Y-%m-%d}-{info['name']}{sfx}.mp3")
                    print(f"  {info['name']} audio uploaded ({mp3.stat().st_size / 1e6:.1f} MB)")
                    break
                except Exception as exc:
                    print(f"  ! {info['name']} upload attempt {attempt} failed: "
                          f"{type(exc).__name__}: {_redact(str(exc))[:200]}")
            if url:
                try:                         # its own podcast-app feed (feed-te.xml / feed-hi.xml)
                    podfeed.publish_language_episode(
                        code, mp3, url.rsplit("/", 1)[-1],
                        f"{info['show']} · {date_str}", f"{info['hosts']} · {report_type.title()}")
                except Exception as exc:
                    print(f"  ! {info['name']} feed not updated: {type(exc).__name__}")
                try:
                    podfeed.prune_extra(f"-{info['name']}{sfx}.mp3", keep=21)
                except Exception as exc:
                    print(f"  ! {info['name']} prune failed: {type(exc).__name__}")
        episodes.append({"kind": code, "label": info["label"], "file": str(mp3), "url": url,
                         "hosts": info["hosts"]})
        if not dry:                                  # previous-podcast memory for tomorrow
            info["archive"].mkdir(parents=True, exist_ok=True)
            script = out_dir / f"script_{info['name']}_podcast.txt"
            if script.exists():
                (info["archive"] / f"{now:%Y-%m-%d}{sfx}-podcast.txt").write_text(script.read_text())
    return episodes


def headlines(md: str, n: int = 3) -> list[str]:
    sec = re.search(r"^##[^\n]*Top[^\n]*\n(.*?)(?=^## )", md, re.S | re.M)
    lines = re.findall(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", sec.group(1) if sec else md, re.M)[:n]
    return [re.sub(r"\[\[[^\]]+\]\]\([^)]+\)|[*_#`]", "", l).strip()[:140] for l in lines]


