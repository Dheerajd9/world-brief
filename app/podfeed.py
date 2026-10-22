"""
Publish each episode so it plays in the browser and in podcast apps, free, using GitHub:
  - MP3s      -> GitHub Release assets (tag "episodes"), oldest pruned
  - web site  -> play.html + feed.xml + audio/ on the `podcast` branch, served by GitHub
                 Pages (Settings -> Pages -> Branch: podcast). The branch only ever holds
                 generated files and is replaced by one fresh commit each time.
The feed is marked <itunes:block>, so it never appears in podcast directories; only someone
with the URL can subscribe.

Needs (skips quietly if missing; then the MP3 is attached to the email instead):
  PODCAST_REPO    owner/repo (template workflow: this repo)
  PODCAST_TOKEN   token with Contents write on that repo (template workflow: GITHUB_TOKEN)
  PODCAST_BRANCH  branch for the site (default "podcast"; never the code branch)
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import requests


def _redact(text: str) -> str:
    text = re.sub(r"bot\d+:[\w-]+", "bot***", text)
    text = re.sub(r"(apikey|key|token)=[^&\s]+", r"\1=***", text, flags=re.I)
    return re.sub(r"github_pat_\w+|gh[pousr]_\w+|AIza[\w-]{20,}", "***", text)

ROOT = Path(__file__).parent
DATA = Path(os.getenv("WB_DATA") or Path(__file__).resolve().parent.parent)   # state, briefs, logs (Docker: /data)
API = "https://api.github.com"
TAG = "episodes"
KEEP = int(os.getenv("PODCAST_KEEP", "45"))   # ~2 weeks of morning+evening+weekly


def gh(method: str, url: str, token: str, **kw) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", **kw.pop("headers", {})}
    r = requests.request(method, url if url.startswith("http") else API + url,
                         headers=headers, timeout=120, **kw)
    if r.status_code >= 400 and r.status_code != 404:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:200]}")
    return r


BRANCH = os.getenv("PODCAST_BRANCH", "podcast").strip() or "podcast"


def ensure_branch(repo: str, token: str) -> None:
    """Create the site branch as an empty orphan (never a copy of the code) if missing."""
    if gh("GET", f"/repos/{repo}/git/ref/heads/{BRANCH}", token).status_code != 404:
        return
    tree = gh("POST", f"/repos/{repo}/git/trees", token, json={"tree": [
        {"path": "README.md", "mode": "100644", "type": "blob",
         "content": "Generated podcast site (World Brief). Do not edit.\n"}]}).json()["sha"]
    commit = gh("POST", f"/repos/{repo}/git/commits", token,
                json={"message": "Podcast site", "tree": tree, "parents": []}).json()["sha"]
    gh("POST", f"/repos/{repo}/git/refs", token, json={"ref": f"refs/heads/{BRANCH}", "sha": commit})
    print(f"  created the '{BRANCH}' branch for the podcast site")


def get_file(repo: str, path: str, token: str) -> tuple[str | None, str | None]:
    ensure_branch(repo, token)
    r = gh("GET", f"/repos/{repo}/contents/{path}", token, params={"ref": BRANCH})
    if r.status_code == 404:
        return None, None
    j = r.json()
    raw = base64.b64decode(j.get("content", ""))
    try:
        return raw.decode(), j["sha"]
    except UnicodeDecodeError:          # binary file (cover.png): only the sha matters
        return None, j["sha"]


def put_file(repo: str, path: str, data: bytes, token: str, msg: str) -> None:
    _, sha = get_file(repo, path, token)
    body = {"message": msg, "content": base64.b64encode(data).decode(), "branch": BRANCH}
    if sha:
        body["sha"] = sha
    gh("PUT", f"/repos/{repo}/contents/{path}", token, json=body)


def release(repo: str, token: str) -> dict:
    r = gh("GET", f"/repos/{repo}/releases/tags/{TAG}", token)
    if r.status_code == 404:
        r = gh("POST", f"/repos/{repo}/releases", token,
               json={"tag_name": TAG, "name": "Podcast episodes",
                     "body": "Audio files for the World Brief podcast feed."})
    return r.json()


def duration_seconds(mp3: Path) -> int:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(mp3)], capture_output=True, text=True)
        return int(float(out.stdout.strip()))
    except Exception:
        return 0


def make_cover(path: Path) -> bool:
    """Simple 1400x1400 cover art (podcast apps require a square image)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    img = Image.new("RGB", (1400, 1400), (18, 52, 86))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 980, 1400, 1400], fill=(255, 153, 51))          # accent band
    d.ellipse([560, 140, 840, 420], outline=(255, 255, 255), width=14)      # globe
    d.ellipse([640, 140, 760, 420], outline=(255, 255, 255), width=8)
    d.line([566, 280, 834, 280], fill=(255, 255, 255), width=8)
    fonts = "/usr/share/fonts/truetype/dejavu/"
    try:
        big = ImageFont.truetype(fonts + "DejaVuSans-Bold.ttf", 150)
        small = ImageFont.truetype(fonts + "DejaVuSans.ttf", 70)
    except OSError:
        big = small = ImageFont.load_default(size=120)
    d.text((700, 600), "WORLD", font=big, fill="white", anchor="mm")
    d.text((700, 780), "BRIEF", font=big, fill="white", anchor="mm")
    d.text((700, 1190), "Daily world news", font=small, fill=(18, 52, 86), anchor="mm")
    img.save(path, "PNG")
    return True


FEEDS = {
    "en": {"feed": "feed.xml", "list": "episodes.json", "title": "World Brief",
           "lang": "en", "desc": "Daily world news podcast: everything important, explained simply, by "
                                 + f"{os.getenv('PODCAST_HOST_A', 'Alex')} and {os.getenv('PODCAST_HOST_B', 'Maya')}."},
    "te": {"feed": "feed-te.xml", "list": "episodes-te.json", "title": "ఈ రోజు వార్తలు · World Brief Telugu",
           "lang": "te", "desc": "రోజువారీ వార్తలు తెలుగులో: భారత్, తెలంగాణ, అమెరికా, ప్రపంచం. రవి, లక్ష్మి."},
    "hi": {"feed": "feed-hi.xml", "list": "episodes-hi.json", "title": "आज की खबरें · World Brief Hindi",
           "lang": "hi", "desc": "रोज़ की खबरें हिंदी में: भारत, अमेरिका और दुनिया। अर्जुन और मीरा।"},
}


def build_feed(repo: str, episodes: list[dict], lang: str = "en") -> str:
    owner, name = repo.split("/")
    site = f"https://{owner.lower()}.github.io/{name}"
    meta = FEEDS[lang]
    cutoff = datetime.now(timezone.utc).timestamp() - SITE_KEEP_DAYS * 86400
    items = []
    for e in episodes:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", e["id"])
        if m and datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                tzinfo=timezone.utc).timestamp() < cutoff:
            continue                       # audio no longer on the site
        url = f"{site}/audio/{e['id']}"     # served as real audio (podcast apps + iPhone)
        items.append(f"""    <item>
      <title>{escape(e['title'])}</title>
      <description>{escape(e['description'])}</description>
      <enclosure url="{escape(url)}" length="{e['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(e['id'])}</guid>
      <pubDate>{e['pubDate']}</pubDate>
      <itunes:duration>{e['duration']}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(meta['title'])}</title>
    <link>{site}/play.html</link>
    <description>{escape(meta['desc'])}</description>
    <language>{meta['lang']}</language>
    <itunes:author>World Brief bot</itunes:author>
    <itunes:image href="{site}/cover.png"/>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""


def publish_language_episode(lang: str, mp3: Path, asset_name: str, title: str,
                             description: str) -> None:
    """Add a Telugu/Hindi episode to its own podcast feed (feed-te.xml / feed-hi.xml)."""
    repo, token = configured()
    meta = FEEDS[lang]
    text, _ = get_file(repo, meta["list"], token)
    episodes = [e for e in (json.loads(text) if text else []) if e["id"] != asset_name]
    episodes.insert(0, {"id": asset_name, "title": title, "description": description,
                        "url": "", "bytes": mp3.stat().st_size,
                        "pubDate": format_datetime(datetime.now(timezone.utc)),
                        "duration": duration_seconds(mp3)})
    episodes = episodes[:KEEP]
    put_file(repo, meta["list"], json.dumps(episodes, indent=1, ensure_ascii=False).encode(),
             token, f"Episode {asset_name}")
    put_file(repo, meta["feed"], build_feed(repo, episodes, lang).encode(), token,
             f"Feed {asset_name}")
    owner, name = repo.split("/")
    print(f"  {lang} podcast feed updated: https://{owner.lower()}.github.io/{name}/{meta['feed']}")


def token_status() -> tuple[str, int | None]:
    """Check PODCAST_TOKEN without changing anything.
    Returns ("ok", days_left), ("bad", None) when GitHub rejects it, or ("unknown", None)."""
    cfg = configured()
    if not cfg:
        return "unknown", None
    repo, token = cfg
    try:
        r = requests.get(f"{API}/repos/{repo}", timeout=30,
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"})
    except Exception:
        return "unknown", None
    if r.status_code in (401, 403):
        return "bad", None
    exp = r.headers.get("github-authentication-token-expiration", "")   # e.g. "2027-10-11 15:20:00 UTC"
    m = re.match(r"(\d{4}-\d{2}-\d{2})", exp)
    if r.status_code == 200 and m:
        days = (datetime.strptime(m.group(1), "%Y-%m-%d").date() - datetime.now(timezone.utc).date()).days
        return "ok", days
    return ("ok" if r.status_code == 200 else "unknown"), None


def configured() -> tuple[str, str] | None:
    repo, token = os.getenv("PODCAST_REPO", "").strip(), os.getenv("PODCAST_TOKEN", "").strip()
    if repo and token and re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        return repo, token
    return None


PLAYER_HTML = (Path(__file__).parent / "player.html").read_text(encoding="utf-8")
_PLAYER_READY = False


_PLAYER_LIVE: bool | None = None


def player_live(base: str) -> bool:
    """Is the web player actually online (GitHub Pages switched on)? Checked once per run;
    if not, emails use the direct MP3 link instead of a link that would show 404."""
    global _PLAYER_LIVE
    if os.getenv("WB_ASSUME_PLAYER") == "1":
        return True
    if _PLAYER_LIVE is None:
        try:
            r = requests.get(base + "play.html", timeout=15)
            _PLAYER_LIVE = r.status_code == 200 and "World Brief" in r.text
        except Exception:
            _PLAYER_LIVE = False
        if not _PLAYER_LIVE:
            print("  ! web player not reachable (is GitHub Pages on?); using direct MP3 links")
    return _PLAYER_LIVE


def player_url(asset_name: str) -> str | None:
    """A simple web page that PLAYS the episode (GitHub release links only offer a download)."""
    cfg = configured()
    if not cfg or not re.fullmatch(r"[\w.-]+\.mp3", asset_name):
        return None
    owner, name = cfg[0].split("/")
    base = f"https://{owner.lower()}.github.io/{name}/"
    return f"{base}play.html?f={asset_name}" if player_live(base) else None


def ensure_player() -> None:
    """Publish/refresh play.html in the public podcast repo (only when it changed)."""
    global _PLAYER_READY
    if _PLAYER_READY:
        return
    repo, token = configured()
    html_page = PLAYER_HTML.replace("__REPO__", repo)
    current, _ = get_file(repo, "play.html", token)
    if current != html_page:
        put_file(repo, "play.html", html_page.encode(), token, "Update web player")
        print("  web player page updated")
    _PLAYER_READY = True


SITE_KEEP_DAYS = int(os.getenv("SITE_AUDIO_DAYS", "10"))


def sync_site_audio(mp3s: list[tuple[Path, str]]) -> bool:
    """Put the MP3s on the GitHub Pages site (audio/<name>), served as real audio (iPhone
    Safari refuses GitHub release downloads inside a player). The site branch is replaced by ONE fresh commit each time (it only holds generated files),
    keeping the last SITE_AUDIO_DAYS days of audio, so the repo never grows. Never raises."""
    cfg = configured()
    if not cfg or not mp3s:
        return False
    repo, token = cfg
    import shutil
    import tempfile
    try:
        ensure_branch(repo, token)
        branch = BRANCH                    # never the code branch: this one is force-replaced
        auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        git = ["git", "-c", f"http.extraHeader=Authorization: Basic {auth}"]
        url = os.getenv("PODCAST_GIT_URL") or f"https://github.com/{repo}.git"   # override: tests only
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            r = subprocess.run(git + ["clone", "-q", "--depth", "1", "--branch", branch, url, str(site)],
                               capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError(_redact(r.stderr)[-300:])
            audio = site / "audio"
            audio.mkdir(exist_ok=True)
            for path, name in mp3s:
                shutil.copyfile(path, audio / name)
            cutoff = datetime.now(timezone.utc).timestamp() - SITE_KEEP_DAYS * 86400
            for old in audio.glob("*.mp3"):
                m = re.match(r"(\d{4}-\d{2}-\d{2})", old.name)
                if m and datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                        tzinfo=timezone.utc).timestamp() < cutoff:
                    old.unlink()
            # List of available episodes for the player's language tabs and episode list.
            (audio / "index.json").write_text(json.dumps(sorted(p.name for p in audio.glob("*.mp3"))))
            run = lambda *a: subprocess.run(list(a), cwd=site, capture_output=True, text=True,
                                            timeout=600, check=True)
            run("git", "checkout", "-q", "--orphan", "fresh")
            run("git", "add", "-A")
            run("git", "-c", "user.name=github-actions[bot]", "-c",
                "user.email=41898283+github-actions[bot]@users.noreply.github.com",
                "commit", "-q", "-m", "Podcast site (latest episodes)")
            r = subprocess.run(git + ["push", "-q", "-f", "origin", f"fresh:{branch}"], cwd=site,
                               capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                raise RuntimeError(_redact(r.stderr)[-300:])
        print(f"  podcast site updated with {len(mp3s)} audio file(s)")
        return True
    except Exception as exc:
        print(f"  ! podcast site audio not updated: {type(exc).__name__}: {_redact(str(exc))[:200]}")
        return False


def upload_asset(path: Path, asset_name: str) -> str:
    """Upload (or replace) one MP3 on the 'episodes' release; return its public URL."""
    repo, token = configured()
    rel = release(repo, token)
    for a in rel.get("assets", []):
        if a["name"] == asset_name:
            gh("DELETE", f"/repos/{repo}/releases/assets/{a['id']}", token)
    upload_url = rel["upload_url"].split("{")[0]
    asset = gh("POST", upload_url, token, params={"name": asset_name},
               headers={"Content-Type": "audio/mpeg"}, data=path.read_bytes()).json()
    try:
        ensure_player()
    except Exception as exc:
        print(f"  ! web player page not updated: {type(exc).__name__}")
    chapters = path.parent / f"chapters_{path.stem}.json"     # skip buttons for the player
    if chapters.exists():
        try:
            put_file(repo, f"chapters/{asset_name}.json", chapters.read_bytes(), token,
                     f"Chapters {asset_name}")
        except Exception as exc:
            print(f"  ! chapters not published: {type(exc).__name__}")
    return asset["browser_download_url"]


def prune_extra(suffix: str, keep: int = 21) -> None:
    """Keep only the newest `keep` assets ending in `suffix` (e.g. Telugu episodes)."""
    repo, token = configured()
    assets = sorted((a for a in release(repo, token).get("assets", [])
                     if a["name"].endswith(suffix)), key=lambda a: a["name"], reverse=True)
    for a in assets[keep:]:
        gh("DELETE", f"/repos/{repo}/releases/assets/{a['id']}", token)


def publish_episode(meta: dict) -> str:
    """Upload the English episode, update feed.xml for podcast apps; return the MP3 URL."""
    repo, token = configured()
    mp3 = Path(meta["file"])
    stamp = datetime.fromisoformat(meta["date"])
    asset_name = f"{stamp:%Y-%m-%d}-{meta['edition']}.mp3"
    url = upload_asset(mp3, asset_name)

    text, _ = get_file(repo, "episodes.json", token)
    episodes = json.loads(text) if text else []
    episodes = [e for e in episodes if e["id"] != asset_name]
    episodes.insert(0, {
        "id": asset_name, "title": meta["title"], "description": meta["description"],
        "url": url, "bytes": mp3.stat().st_size,
        "pubDate": format_datetime(stamp), "duration": duration_seconds(mp3)})
    keep, drop = episodes[:KEEP], {e["id"] for e in episodes[KEEP:]}
    if drop:
        for a in release(repo, token).get("assets", []):
            if a["name"] in drop:
                gh("DELETE", f"/repos/{repo}/releases/assets/{a['id']}", token)
    if get_file(repo, "cover.png", token)[1] is None:
        cover = DATA / "out" / "cover.png"
        if make_cover(cover):
            put_file(repo, "cover.png", cover.read_bytes(), token, "Add cover art")
    put_file(repo, "episodes.json", json.dumps(keep, indent=1, ensure_ascii=False).encode(),
             token, f"Episode {asset_name}")
    put_file(repo, "feed.xml", build_feed(repo, keep, "en").encode(), token, f"Feed {asset_name}")
    owner, name = repo.split("/")
    print(f"  podcast feed updated: https://{owner.lower()}.github.io/{name}/feed.xml")
    return url


def main() -> None:
    """CLI: publish out/episode.json (normally digest.py calls publish_episode itself)."""
    meta_path = DATA / "out" / "episode.json"
    if not configured():
        print("Podcast feed: PODCAST_REPO / PODCAST_TOKEN not set, skipping.")
        return
    if not meta_path.exists():
        print("Podcast feed: no episode today, skipping.")
        return
    publish_episode(json.loads(meta_path.read_text()))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:        # feed problems must never fail the daily run
        print(f"! podcast feed failed: {type(exc).__name__}: {_redact(str(exc))[:200]}", file=sys.stderr)
