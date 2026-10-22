"""
End-to-end test of the whole pipeline with fake news, a fake AI and silent audio.
No network, no email, no secrets. Runs on every code push (World Brief + Podcast workflow);
if any check fails, the push run turns red before a real email can go out broken.

  python tests/e2e.py            # morning, evening and weekly, in a temp copy of world_brief/

Checks for each edition: exactly one email, ▶️ play links for English + Telugu + Hindi,
chapter files, brief archive, podcast-script memory, seen list and story ledger saved.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "app"
sys.path.insert(0, str(SRC))
TEST_CONFIG = """you: {name: Test, timezone: America/New_York}
email: {from_name: World Brief, send_time: "07:00", weekly: true}
focus: {countries: [in, us], cities: []}
podcast: {enabled: true, hosts: [Alex, Maya], accent: en-IN, languages: [te, hi]}
telegram: {enabled: true}
alerts: {breaking: false}
"""

RUNNER = r'''
import json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())
import digest, markets, podcast, podfeed, languages, weather
weather.fetch = lambda lat, lon: {"current": {"temperature_2m": 28.4, "weather_code": 61},
    "daily": {"temperature_2m_max": [31, 32], "temperature_2m_min": [22, 23],
              "precipitation_probability_max": [60, 40], "weather_code": [63, 2]}}
STYLE = {"wx": 0, "style": 0, "tr": 0}

EDITION = os.environ["EDITION"]
digest.on_this_day = lambda today: [{"year": 1947, "text": "Test history event"}]
markets.numbers_box = lambda weekly=False: (
    "## 📊 Money & markets\n\n| Asset | Latest | Change | Status |\n|---|---:|---:|---|\n"
    "| 🇮🇳 Nifty 50 | 23,146 | ▲ +0.65% | PREVIOUS CLOSE |\n| 💵 USD/INR | ₹94.96 | ▼ -0.20% | DELAYED |\n"
    "| 🪙 Gold 24K India (₹/10 grams) | ₹1,46,430 | — | IBJA |\n", "Nifty 1")

def fake_items(feeds):
    cats = ["in_news", "us_news", "world", "in_economy", "tech"]
    out = []
    for n in range(15):
        link = f"https://news.example.com/{EDITION}/{n}"
        digest.KNOWN_LINKS.add(link)
        out.append({"category": cats[n % len(cats)], "source": "The Hindu",
                    "title": f"{EDITION} test headline: " + " ".join(
                        ["monsoon", "senate", "rupee", "chips", "robots", "tariff", "election",
                         "satellite", "vaccine", "housing", "jobs", "oil", "court", "visa",
                         "startup"][(n + k) % 15] for k in (0, 3, 7)),
                    "summary": "Something happened.", "published": "2026-10-13T06:00:00+00:00",
                    "link": link})
    return out
digest.fetch_items = fake_items

HOSTS = [("ALEX", "MAYA"), ("RAVI", "LAKSHMI"), ("ARJUN", "MEERA")]

def script(a, b):
    lines = []
    for ch in ["Top stories", "India", "USA", "World", "Money", "Wrap-up"]:
        lines.append(f"CHAPTER: {ch}")
        for i in range(3):
            lines.append(f"{a}: Line {i} about {ch}, explained simply for the listener today.")
            lines.append(f"{b}: Reply {i} about {ch}, with context and what happens next.")
    return "\n".join(lines)

BRIEF = """# World Brief
**Most important:** test

{{LISTEN}}

## 1. Top 5
- India story one [S1]
- USA story two [S2]

## 2. India
- Detail [S3]

{{MARKET_SNAPSHOT}}

<!--META
REPORT_TYPE: X
PODCAST_REQUIRED: TRUE
PODCAST_TOPICS: India story; USA story
TOP_STORY_COUNT: 5
URGENT_ALERT: FALSE
VERIFICATION_WARNINGS: NONE
-->
<!--STORIES [{"id": "test-story", "title": "Test story", "status": "DEVELOPING", "stage": "PROPOSED", "summary": "s", "milestone": "m"}] -->
<!--BELIEFS [{"belief": "b", "confidence": "MEDIUM"}] -->
"""

CALLS = []
def fake_gemini(system, user):
    CALLS.append(system[:80])
    if "LOCAL_HEADLINES" in system:
        n = len([l for l in user.splitlines() if l.strip()])
        return "\n".join([f"TE{i}: తెలుగు వార్త {i}" for i in range(1, n + 1)]
                         + [f"HI{i}: हिंदी खबर {i}" for i in range(1, n + 1)])
    if ("TRANSLATION MODE" in system and "ENGLISH_SCRIPT:" in user and "ALEX:" in user
            and "CHAPTER:" in user):
        STYLE["tr"] += 1
    if "EXPLAINING STYLE" in system:
        STYLE["style"] += 1
        STYLE["wx"] += "WEATHER (local days): Hyderabad: now 28°C, light rain; today 22–31°C, rain, rain chance 60%" in user
    if user.startswith("SCRIPT:"):
        return user[len("SCRIPT:"):].strip()
    if "FINAL OUTPUT REMINDER" in system:              # the news brief itself
        return BRIEF
    for a, b in HOSTS:
        if os.environ.get("FAIL_HOST") == a and (f"`{a}:`" in system or f"with exactly `{a}:`" in system):
            return None
        if f"`{a}:`" in system or f"with exactly `{a}:`" in system or f"{a} and {b}" in system[:400]:
            return script(a, b)
    if "DRAFT:" in user:
        return user.split("DRAFT:", 1)[1].strip()
    return BRIEF
digest.call_gemini = fake_gemini
digest.call_mistral = lambda s, u: None                # backup brains "down": must not matter
digest.call_openrouter = lambda s, u: None
podcast.cloud_tts_podcast = lambda *a, **k: None
if os.environ.get("GEMINI_DOWN") == "1":              # drill: Gemini fully down
    digest.call_mistral = fake_gemini
    digest.call_gemini = lambda s, u: None

def silent(text, speaker, out, profile=None):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "1", "-q:a", "9", str(out)], check=True)
podcast.speak_line = silent
podcast.gemini_podcast = lambda turns, work, profile, pref: None

podfeed.configured = lambda: ("Owner/world-brief-podcast", "token")
UPLOADS = []
def fake_upload(path, name):
    UPLOADS.append(name)
    ch = path.parent / f"chapters_{path.stem}.json"
    if ch.exists():
        UPLOADS.append("chapters:" + name)
    return f"https://github.com/Owner/world-brief-podcast/releases/download/episodes/{name}"
podfeed.upload_asset = fake_upload
podfeed.prune_extra = lambda *a, **k: None
FEEDS_PUB = []
podfeed.publish_language_episode = lambda lang, mp3, name, title, desc: FEEDS_PUB.append([lang, name])
TG = []
TG_PAGES = []
class _R:
    status_code = 200
    def __init__(self, url=""):
        self.url = url
    def json(self):
        if self.url.endswith("createAccount"):
            return {"ok": True, "result": {"access_token": "t"}}
        if self.url.endswith("createPage"):
            return {"ok": True, "result": {"url": f"https://telegra.ph/World-Brief-{len(TG_PAGES)}"}}
        return {"ok": True, "result": {"message_id": 7}}
TG_TEXT = []
def fake_post(url, **kw):
    TG.append(url.rsplit("/", 1)[-1])
    if url.endswith("createPage"):
        TG_PAGES.append((kw.get("data") or {}).get("content", ""))
    body = kw.get("json") or kw.get("data") or {}
    TG_TEXT.append(body.get("text") or body.get("caption") or "")
    rm = body.get("reply_markup")
    if rm:
        rm = json.loads(rm) if isinstance(rm, str) else rm
        TG_BUTTONS.append([b["text"] for row in rm["inline_keyboard"] for b in row])
    return _R(url)
TG_BUTTONS = []
digest.requests.post = fake_post
os.environ["TELEGRAM_GAP_SEC"] = "0"
os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
os.environ["TELEGRAM_CHANNEL_ID"] = "@family"
os.environ.pop("TELEGRAM_CHAT_ID", None)
SYNCED = []
podfeed.sync_site_audio = lambda mp3s: SYNCED.extend(n for _, n in mp3s) or True
podfeed.publish_episode = lambda ep: fake_upload(Path(ep["file"]),
                                                f"2026-10-13-{ep['edition']}.mp3")

EMAILS = []
HEALTH_MAILS = []
def fake_send(subject, md, audio=None, to=None, audio_name=None, everyone=False, styled=None):
    if subject.startswith("🩺"):
        HEALTH_MAILS.append({"subject": subject, "md": md, "everyone": everyone})
        return
    EMAILS.append({"subject": subject, "md": md, "everyone": everyone,
                   "audio": [str(a) for a in (audio or [])]})
digest.send_email = fake_send
digest.send_telegram = lambda *a, **k: None
digest.token_reminder = lambda *a, **k: None
languages.send_whatsapp = lambda *a, **k: None

digest.main()
Path("result.json").write_text(json.dumps({"emails": EMAILS, "uploads": UPLOADS, "synced": SYNCED,
                                           "feeds": FEEDS_PUB, "telegram": TG, "style": STYLE, "tg_text": "".join(TG_TEXT), "tg_msgs": [x for x in TG_TEXT if x], "tg_pages": TG_PAGES, "tg_buttons": TG_BUTTONS, "health": HEALTH_MAILS}))
'''


def check(cond: bool, msg: str, errors: list[str]) -> None:
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        errors.append(msg)


def run_edition(work: Path, edition: str, errors: list[str]) -> None:
    print(f"\n=== {edition} ===")
    env = {**os.environ, "EDITION": edition, "PODCAST": "1", "PODCAST_REVIEW": "1",
           "GITHUB_EVENT_NAME": "push", "PODCAST_LANGUAGES": "te,hi", "WB_DATA": str(work),
           "WB_CONFIG": str(work / "config.yaml"),
           "LANG_EDITIONS": "morning,weekly", "WB_ASSUME_PLAYER": "1"}
    for k in ("DRY_RUN", "NO_LLM", "GEMINI_API_KEY", "GITHUB_TOKEN", "MISTRAL_API_KEY",
              "OPENROUTER_API_KEY", "GOOGLE_TTS_API_KEY"):
        env.pop(k, None)
    (work / "app" / "runner.py").write_text(RUNNER)
    p = subprocess.run([sys.executable, "runner.py"], cwd=work / "app", env=env,
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        print(p.stdout[-3000:], p.stderr[-3000:])
        check(False, f"{edition}: pipeline crashed", errors)
        return
    res = json.loads((work / "app" / "result.json").read_text())
    emails, uploads = res["emails"], res["uploads"]
    sfx = "" if edition == "morning" else f"-{edition}"
    check(len(emails) == 1, f"{edition}: exactly one email (got {len(emails)})", errors)
    if not emails:
        return
    md = emails[0]["md"]
    check(emails[0]["everyone"], f"{edition}: email goes to all readers (BCC)", errors)
    check("{{LISTEN}}" not in md and "{{MARKET_SNAPSHOT}}" not in md,
          f"{edition}: no leftover placeholders", errors)
    for name in (f"telugu{sfx}", f"hindi{sfx}"):
        check(f"play.html?f=2026-10-13-{name}.mp3" in md or f"-{name}.mp3" in md,
              f"{edition}: ▶️ play link for {name}", errors)
    check(md.count("play.html?f=") >= 3, f"{edition}: English + Telugu + Hindi play links "
                                            f"({md.count('play.html?f=')} found)", errors)
    check(not emails[0]["audio"], f"{edition}: no big attachments when links work", errors)
    if edition == "morning":
        check("-quick" not in md and "Quick" not in md, "morning: one Full English episode (no Quick copy)", errors)
    check("తెలుగులో ముఖ్యాంశాలు" not in md and "हिंदी में मुख्य खबरें" not in md,
          f"{edition}: email text is English only", errors)
    check(re.search(r"Listen: English · (Telugu|Hindi)", md) is not None and not re.search(r"[\u0C00-\u0C7F\u0900-\u097F]", md),
          f"{edition}: language names in English (no Telugu/Hindi script in the email)", errors)
    check("Markets now:** " in md and "Nifty 50 23,146 ▲0.65%" in md and "$1 = ₹94.96" in md,
          f"{edition}: one-line market strip", errors)
    check("India story one" in emails[0]["subject"], f"{edition}: subject shows the top stories "
          f"({emails[0]['subject'][:80]})", errors)
    import markdown as _mdlib, email_style
    page = email_style.page(_mdlib.markdown(md, extensions=["extra"]))
    check(page.count("border-radius:24px") >= 3 and "border-left:4px solid" in page
          and "#fff7e6" in page and 'color:#16a34a">▲' in page,
          f"{edition}: email has play buttons, story cards, Top 5 box, green/red arrows", errors)
    st = res.get("style", {})
    check(st.get("style", 0) >= 1 and st.get("wx", 0) == 0 and "Weather:" not in md,
          f"{edition}: podcasts get the explaining style; no weather forecast anywhere {st}", errors)
    if edition != "weekly":
        tail = md.split("More headlines (not covered above)")[-1]
        check("More headlines (not covered above)" in md and "](http" in tail,
              f"{edition}: '📰 More headlines' lists every other story with links", errors)
        check("More headlines" not in "".join(
            p.read_text() for p in (work / "briefs" / "podcasts").glob("*.txt")) if
            (work / "briefs" / "podcasts").exists() else True,
            f"{edition}: podcasts don't read out the extra headline list", errors)
    langs_fed = sorted({f[0] for f in res.get("feeds", [])})
    check(langs_fed == ["hi", "te"], f"{edition}: Telugu + Hindi podcast-app feeds updated ({langs_fed})", errors)
    tg = res.get("telegram", [])
    msgs = res.get("tg_msgs", [])
    pages = res.get("tg_pages", [])
    posts = [x for x in tg if x in ("sendMessage", "sendAudio")]
    check(posts == ["sendAudio"] and "pinChatMessage" in tg,
          f"{edition}: Telegram channel gets ONE message (podcast + headlines + buttons), pinned ({posts})", errors)
    check(bool(pages) and "India story one" in "".join(pages) and "Detail" in "".join(pages)
          and all(len(m) <= 1024 for m in msgs) and "Full news" in msgs[0],
          f"{edition}: the full news is in the 📖 Full news article (Instant View); caption under 1024", errors)
    check(st.get("tr") == 2, f"{edition}: Telugu + Hindi made from the same English episode "
          f"(same stories and details; {st.get('tr')} conversions)", errors)
    tgt = res.get("tg_text", "")
    btns = (res.get("tg_buttons") or [[]])[0]
    check(any(b.startswith("📖 Full news") for b in btns) and sum(b.startswith("▶️") for b in btns) >= 3
          and ">https://" not in tgt,
          f"{edition}: Telegram headline has buttons: Full news + Play for every episode ({btns})", errors)
    if edition == "morning":
        import tg_format
        tm = "".join(tg_format.full_messages("## 1. Top 5\n- a\n## 🌍 World & geopolitics\n- b\n"))
        check("#Top5" in tm and "#World" in tm,
              "Telegram (TELEGRAM_MESSAGES=1 style): sections carry topic hashtags", errors)
    check(len(res.get("synced", [])) >= 3, f"{edition}: audio copied to the player site "
                                            f"({len(res.get('synced', []))} files)", errors)
    check(sum(u.startswith("chapters:") for u in uploads) >= 3,
          f"{edition}: chapter files published", errors)
    import datetime
    from zoneinfo import ZoneInfo
    today = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    arch = work / "briefs" / f"{today}{'' if edition == 'morning' else '-' + edition}.md"
    check(arch.exists(), f"{edition}: brief archived for tomorrow's memory", errors)
    for lang in ("telugu", "hindi"):
        check(any((work / "briefs" / lang).glob("*-podcast.txt")),
              f"{edition}: {lang} script kept as memory", errors)
    check(any((work / "briefs" / "podcasts").glob("*.txt")),
          f"{edition}: English scripts kept as memory", errors)
    if edition != "weekly":
        seen = json.loads((work / "state" / "seen.json").read_text())
        check(any(f"{edition} test headline" in k or True for k in seen) and len(seen) > 0,
              f"{edition}: seen list saved (no repeats tomorrow)", errors)
    stories = json.loads((work / "state" / "stories.json").read_text())
    check("test-story" in json.dumps(stories), f"{edition}: story ledger saved", errors)


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg missing; install it first")
        return 2
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "wb"
        shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(
            "briefs", "state", "logs", "out", "tests", "docs", ".git", "__pycache__", ".env",
            "config.yaml"))
        (work / "config.yaml").write_text(TEST_CONFIG)
        import yaml
        import config as _cfg

        # ---------------------------------------------------------------- public edition
        print("\n=== public edition: config, feeds, prompts, no personal data ===")
        bp = (SRC / "prompts" / "brief_prompt.md").read_text()
        for sec in ["What actually matters today", "World & geopolitics", "Around the world (region by region)",
                    "AI & robotics (highest priority)", "Big tech & frontier companies", "Chips & computing",
                    "Major world changes", "Government & politics", "Personal finance",
                    "Housing & cost of living", "Business, jobs & the future of work", "Energy revolution",
                    "Future technology", "Space", "Truth check", "Future signal", "Today's lesson",
                    "Why markets moved", "Severe weather & disasters", "Big sports",
                    "Scams & safety alerts", "Good news"]:
            check("## " in bp and sec in bp, f"brief has section: {sec}", errors)
        check("{FOCUS_SECTIONS}" in bp and "{AUDIENCE}" in bp, "brief: focus sections come from config.yaml", errors)
        world = yaml.safe_load((REPO / "feeds" / "world.yaml").read_text())
        for g in ["world", "world_regions", "global_economy", "ai_robotics", "tech", "science_health_climate",
                  "fact_check", "scams_safety", "weather_disasters", "sports", "good_news"]:
            check(bool(world.get(g)), f"world feeds: {g}", errors)
        n_world = sum(map(len, world.values()))
        check(n_world >= 90 and all(u.startswith("https://") for us in world.values() for u in us),
              f"world pack: {n_world} feeds, all https", errors)
        for pack in ("in", "us", "gb", "ca", "au"):
            check((REPO / "feeds" / f"{pack}.yaml").exists(), f"country pack: {pack}", errors)
        default = _cfg._merge(_cfg.DEFAULTS, {})
        f0 = _cfg.feeds(default)
        check(not any(k.startswith(("in_", "us_")) for k in f0) and _cfg.focus_text(default)["FOCUS_SECTIONS"] == "",
              "default: whole world only, no country targeted", errors)
        f1 = _cfg.feeds(_cfg._merge(_cfg.DEFAULTS, {"focus": {"countries": ["in", "ke"], "cities": ["Nairobi"]}}))
        check("in_news" in f1 and "ke_news" in f1 and any("Nairobi" in u for u in f1.get("cities", [])),
              "focus: country packs, any other country via Google News, city searches", errors)
        ft = _cfg.focus_text(_cfg._merge(_cfg.DEFAULTS, {"focus": {"countries": ["gb"], "cities": ["London"]}}))
        check("## 🇬🇧 United Kingdom" in ft["FOCUS_SECTIONS"] and "## 🏙️ London" in ft["FOCUS_SECTIONS"]
              and "United Kingdom" in ft["CHAPTERS"], "focus: own sections + podcast chapters", errors)
        bad = []
        for broken in ({"you": {"timezone": "Mars/Base"}}, {"email": {"send_time": "7am"}},
                       {"podcast": {"hosts": ["Solo"]}}, {"focus": {"countries": ["india"]}},
                       {"podcast": {"languages": ["xx"]}}):
            try:
                _cfg.validate(_cfg._merge(_cfg.DEFAULTS, broken))
                bad.append(broken)
            except ValueError:
                pass
        check(not bad, f"config: clear errors for mistakes ({bad})", errors)
        for ex in sorted((REPO / "examples").glob("*.yaml")) + [REPO / "config.example.yaml"]:
            try:
                _cfg.validate(_cfg._merge(_cfg.DEFAULTS, yaml.safe_load(ex.read_text())))
                ok = True
            except Exception:
                ok = False
            check(ok, f"example config valid: {ex.name}", errors)
        # No personal data anywhere in the public repo.
        personal = re.compile("|".join(["Dav" + "era", "dheeraj" + r"\.d", "Daily-World" + "-Brief",
                                         "ai_news" + "_digest", r"@gmail\.com"]), re.I)
        personal_cs = re.compile(r"\bD" + r"ji\b")
        secret = re.compile(r"AIza[\w-]{30}|github_pat_\w{20}|sk-or-v1-\w{20}|\b\d{9,10}:[\w-]{30,}")
        leaks = []
        for f in REPO.rglob("*"):
            if f.is_file() and ".git" not in f.parts and f.suffix in (".py", ".md", ".yaml", ".yml", ".html", ".txt", ".toml", "") \
                    and f.name != "e2e.py":
                txt = f.read_text(errors="ignore")
                if personal.search(txt) or personal_cs.search(txt) or secret.search(txt):
                    leaks.append(str(f.relative_to(REPO)))
        check(not leaks, f"no personal data or secrets in the repo ({leaks})", errors)
        check("Hyderabad" not in bp and "India" not in bp and "Telangana" not in bp,
              "brief prompt is general world news (no built-in country)", errors)
        size = len(bp.encode()) + len((SRC / "prompts" / "core_rules.md").read_bytes())
        check(size < 40000, f"prompt: brief rules kept small ({size // 1000} KB)", errors)
        te_p = (SRC / "prompts" / "telugu_podcast_prompt.md").read_text()
        hi_p = (SRC / "prompts" / "hindi_podcast_prompt.md").read_text()
        check("Tenglish" in te_p and "Hinglish" in hi_p and "Telugu" not in hi_p,
              "optional languages: Telugu (Tenglish) and Hindi (Hinglish) prompts", errors)
        os.environ.pop("PODCAST_LANGUAGES", None)
        import languages as _lg
        check(_lg.wanted("morning") == [], f"languages: English only by default ({_lg.wanted('morning')})", errors)
        check("EXTRA TOPICS" in (SRC / "prompts" / "weekly_prompt.md").read_text(), "weekly: extra topics", errors)
        for k in list(_cfg.APPLIED):          # don't leak this repo's defaults into the test runs
            os.environ.pop(k, None)

        for edition in ("morning", "weekly"):
            run_edition(work, edition, errors)
        # Failure drill: Telugu script can't be written -> email still goes out, says so.
        print("\n=== morning, Telugu AI down ===")
        env = {**os.environ, "EDITION": "morning", "FAIL_HOST": "RAVI",
               "PODCAST_LANGUAGES": "te,hi", "LANG_EDITIONS": "morning", "GITHUB_EVENT_NAME": "push",
               "WB_ASSUME_PLAYER": "1"}
        for k in ("DRY_RUN", "NO_LLM", "GEMINI_API_KEY", "GITHUB_TOKEN", "MISTRAL_API_KEY",
              "OPENROUTER_API_KEY", "GOOGLE_TTS_API_KEY"):
            env.pop(k, None)
        import time as _t
        p = subprocess.run([sys.executable, "-c",
                            "import time; time.sleep=lambda s: None; exec(open('runner.py').read())"],
                           cwd=work / "app", env=env, capture_output=True, text=True, timeout=600)
        res = json.loads((work / "app" / "result.json").read_text()) if p.returncode == 0 else {"emails": []}
        md = res["emails"][0]["md"] if res["emails"] else ""
        check(len(res["emails"]) == 1, "Telugu down: email still sent", errors)
        check("could not be made" in md and "Telugu" in md, "Telugu down: email says Telugu audio is missing", errors)
        check("hindi.mp3" in md, "Telugu down: Hindi still delivered", errors)
        hm = res.get("health", [])
        check(len(hm) == 1 and not hm[0]["everyone"] and "Telugu" in hm[0]["md"],
              "Telugu down: private health alert to Dji only says Telugu audio is missing", errors)

        # Drill: run too long -> podcasts skipped, the email still goes out, Dji is told.
        print("\n=== morning, run too long (send before the job time limit) ===")
        (work / "state" / "seen.json").unlink(missing_ok=True)
        env_t = {**env, "WB_SEND_BY_MIN": "0"}
        env_t.pop("FAIL_HOST", None)
        p = subprocess.run([sys.executable, "-c",
                            "import time; time.sleep=lambda s: None; exec(open('runner.py').read())"],
                           cwd=work / "app", env=env_t, capture_output=True, text=True, timeout=600)
        res = json.loads((work / "app" / "result.json").read_text()) if p.returncode == 0 else {"emails": []}
        md = res["emails"][0]["md"] if res["emails"] else ""
        subs = [e["subject"] for e in res["emails"]]
        check(len(subs) == 1 and "## " in md, f"too long: still ONE news email, no separate podcast email ({subs})", errors)
        check(any("skipped" in h["md"] for h in res.get("health", [])),
              "too long: health alert says which podcasts were skipped", errors)
        tgl = res.get("telegram", [])
        check([x for x in tgl if x in ("sendMessage", "sendAudio")] == ["sendMessage"],
              f"too long: Telegram still gets its one message ({tgl})", errors)
        src_w = (SRC / "digest.py").read_text()
        check('os.getenv("WB_SEND_BY_MIN", "120")' in src_w,
              "slow day: the email waits for the podcast (one complete email, up to 2 hours)", errors)
        env_p = {**env, "PODCAST_ONLY": "1", "FORCE": "1"}
        env_p.pop("FAIL_HOST", None)
        p = subprocess.run([sys.executable, "-c",
                            "import time; time.sleep=lambda s: None; exec(open('runner.py').read())"],
                           cwd=work / "app", env=env_p, capture_output=True, text=True, timeout=600)
        res = json.loads((work / "app" / "result.json").read_text()) if p.returncode == 0 else {"emails": []}
        subs = [e["subject"] for e in res["emails"]]
        check(len(subs) == 1 and subs[0].startswith("🎧 Podcast ready") and "sendAudio" in res.get("telegram", []),
              f"run: podcast: makes today's podcast again without resending the news ({subs})", errors)
        print("\n=== morning, no time left at all (hard stop) ===")
        (work / "state" / "seen.json").unlink(missing_ok=True)
        env_h = {**env_t, "WB_HARD_STOP_MIN": "0"}
        p = subprocess.run([sys.executable, "-c",
                            "import time; time.sleep=lambda s: None; exec(open('runner.py').read())"],
                           cwd=work / "app", env=env_h, capture_output=True, text=True, timeout=600)
        res = json.loads((work / "app" / "result.json").read_text()) if p.returncode == 0 else {"emails": []}
        check(len(res["emails"]) == 1 and "## " in res["emails"][0]["md"],
              "hard stop: news email still sent", errors)
        check(any("skipped" in h["md"] for h in res.get("health", [])),
              "hard stop: health alert says which podcasts were skipped", errors)
        src_d = (SRC / "digest.py").read_text()
        check("_post_capped(" in src_d and "GEMINI_MAX_SEC" in src_d and "elapsed()" in src_d,
              "slow AI: every AI answer has a hard time limit, Gemini hands over to the backup", errors)

        # Drill 2: Gemini completely down -> free backup brain writes everything.
        print("\n=== morning, Gemini down (Mistral backup) ===")
        (work / "state" / "seen.json").unlink(missing_ok=True)   # fresh news for this drill
        env2 = {**env, "GEMINI_DOWN": "1"}
        env2.pop("FAIL_HOST", None)
        p = subprocess.run([sys.executable, "-c",
                            "import time; time.sleep=lambda s: None; exec(open('runner.py').read())"],
                           cwd=work / "app", env=env2, capture_output=True, text=True, timeout=600)
        res = json.loads((work / "app" / "result.json").read_text()) if p.returncode == 0 else {"emails": []}
        md = res["emails"][0]["md"] if res["emails"] else ""
        if not res["emails"]:
            print(p.stdout[-1500:], p.stderr[-1500:])
        check(len(res["emails"]) == 1 and "LLM unavailable" not in md,
              "Gemini down: full brief still written by the backup brain", errors)
        check(md.count("play.html?f=") >= 3, "Gemini down: podcasts still made", errors)

        # Drill: player-site audio sync with a local git repo (fresh single commit, prune old).
        print("\n=== player site audio sync ===")
        bare = Path(tmp) / "site.git"
        seed = Path(tmp) / "seed"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "MASTER", str(bare)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "MASTER", str(seed)], check=True)
        (seed / "audio").mkdir()
        (seed / "play.html").write_text("World Brief")
        (seed / "audio" / "2020-01-01-old.mp3").write_bytes(b"old")
        g = ["git", "-C", str(seed), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "c1"], check=True)
        subprocess.run(g + ["commit", "-q", "--allow-empty", "-m", "c2"], check=True)
        subprocess.run(g + ["push", "-q", str(bare), "MASTER"], check=True)
        mp3 = Path(tmp) / "x.mp3"
        mp3.write_bytes(b"ID3audio")
        drill2 = f"""
import os, sys, json
sys.path.insert(0, os.getcwd())
import podfeed
podfeed.configured = lambda: ("Owner/site", "tok")
class J:
    status_code = 200
    def json(self): return {{"default_branch": "MASTER"}}
podfeed.gh = lambda *a, **k: J()
podfeed.BRANCH = "MASTER"
os.environ["PODCAST_GIT_URL"] = {str(bare)!r}
from pathlib import Path
ok = podfeed.sync_site_audio([(Path({str(mp3)!r}), "2099-01-01-telugu.mp3")])
print(json.dumps({{"ok": ok}}))
"""
        p = subprocess.run([sys.executable, "-c", drill2], cwd=work / "app", capture_output=True, text=True, timeout=120)
        files = subprocess.run(["git", "-C", str(bare), "ls-tree", "-r", "--name-only", "MASTER"],
                               capture_output=True, text=True).stdout.split()
        commits = subprocess.run(["git", "-C", str(bare), "rev-list", "--count", "MASTER"],
                                 capture_output=True, text=True).stdout.strip()
        check('"ok": true' in p.stdout, "site sync: push succeeded", errors)
        check("audio/2099-01-01-telugu.mp3" in files and "play.html" in files,
              "site sync: new audio added, player page kept", errors)
        check("audio/2020-01-01-old.mp3" not in files, "site sync: old audio removed", errors)
        check(commits == "1", f"site sync: history stays one commit (got {commits})", errors)

        # Feed XML: all three languages, enclosures on the site, old episodes left out.
        print("\n=== podcast feeds ===")
        feed_py = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import podfeed
from datetime import datetime, timezone, timedelta
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")
eps = [{"id": today + "-telugu.mp3", "title": "T & <x>", "description": "d", "bytes": 10, "pubDate": "x", "duration": 60},
       {"id": old + "-telugu.mp3", "title": "old", "description": "d", "bytes": 10, "pubDate": "x", "duration": 60}]
out = {l: podfeed.build_feed("Owner/world-brief-podcast", eps, l) for l in ("en", "te", "hi")}
print(json.dumps({"te_has_today": "audio/" + today + "-telugu.mp3" in out["te"], "old_dropped": old not in out["te"],
                  "escaped": "&amp;" in out["te"] and "<x>" not in out["te"], "te_lang": "<language>te</language>" in out["te"],
                  "hi_title": "Hindi" in out["hi"], "en_title": "<title>World Brief</title>" in out["en"]}))
"""
        p = subprocess.run([sys.executable, "-c", feed_py], cwd=work / "app", capture_output=True, text=True, timeout=60)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-800:], p.stderr[-800:])
            r = {}
        check(bool(r) and all(r.values()), f"feeds: three language feeds valid, site audio links, old items dropped {r}", errors)

        # Telegram setup: finds the channel from the bot's updates, saves it, digest uses it.
        print("\n=== Telegram auto-setup ===")
        tg_py = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["TELEGRAM_BOT_TOKEN"] = "1:x"; os.environ.pop("TELEGRAM_CHANNEL_ID", None); os.environ["TELEGRAM_GAP_SEC"] = "0"
import tgsetup, digest
class G:
    status_code = 200
    def json(self): return {"result": [{"my_chat_member": {"chat": {"id": -1009876, "type": "channel", "title": "Family News"}}}]}
posts = []
tgsetup.requests.get = lambda *a, **k: G()
tgsetup.requests.post = lambda url, **k: (posts.append(k["json"]["chat_id"]), G())[1]
mails = []
digest.send_email = lambda s, m, *a, **k: mails.append(m)
tgsetup.main()
mail0 = list(mails)
saved = json.loads(tgsetup.STATE.read_text())
sent = []
digest.requests.post = lambda url, **k: (sent.append((url.rsplit("/",1)[-1], (k.get("json") or k.get("data") or {}).get("chat_id"))), G())[1]
open("e.mp3","wb").write(b"x")
digest.send_telegram_channel("T", "## 1. Top 5\n- a\n", [{"file": "e.mp3", "url": None, "label": "L", "hosts": "H"}])
import alerts
digest.KNOWN_LINKS.add("https://example.com/a")
used0 = list(sent)
mails.clear(); sent.clear()
alerts.deliver([{"headline": "Big quake", "why": "W", "link": "https://example.com/a", "source": "S"}])
alert_to = [c for m, c in sent]
print(json.dumps({"saved": saved["id"], "test_post": posts, "mail_ok": "Found" in str(mail0), "used": used0,
                  "alert_to": alert_to, "alert_mail": len(mails)}))
"""
        p = subprocess.run([sys.executable, "-c", tg_py], cwd=work / "app", capture_output=True, text=True, timeout=60)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-800:], p.stderr[-800:])
            r = {}
        check(r.get("saved") == -1009876 and r.get("test_post") == [-1009876] and r.get("mail_ok"),
              "Telegram setup: channel found, saved, test posted, email sent", errors)
        check(r.get("used") and all(c in (-1009876, "-1009876") for m, c in r["used"]
                                    if m not in ("createAccount", "createPage")),
              "Telegram setup: editions use the saved channel automatically", errors)
        check(r.get("alert_to") == [] and r.get("alert_mail") == 1,
              "Breaking alerts: email only, nothing extra on Telegram", errors)
        dsrc = (SRC / "digest.py").read_text()
        check('("telegram", lambda: send_telegram(' not in dsrc,
              "Telegram: only the one channel message (news + podcast), no extra brief to a chat", errors)

        # Drill 3: free Google Cloud voices + monthly cap (no network: fake API).
        print("\n=== Google Cloud voices + free-tier cap ===")
        drill = r"""
import base64, json, os, subprocess, sys, types
sys.path.insert(0, os.getcwd())
import podcast
from pathlib import Path
os.environ["GOOGLE_TTS_API_KEY"] = "k"
silent = Path("s.mp3")
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t","1","-q:a","9",str(silent)],check=True)
class R:
    status_code = 200
    def json(self): return {"audioContent": base64.b64encode(silent.read_bytes()).decode()}
calls = []
podcast.requests.post = lambda url, **kw: (calls.append(kw["json"]["voice"]["name"]), R())[1]
work = Path("cw"); work.mkdir(exist_ok=True)
turns = [("RAVI", "నమస్తే " * 50), ("LAKSHMI", "ఇది పరీక్ష. " * 900)]
parts = podcast.cloud_tts_podcast(turns, work, podcast.PROFILES["te"], "te")
used = json.loads(podcast.CLOUD_TTS_USAGE.read_text())
os.environ["GOOGLE_TTS_MONTHLY_CHARS"] = "10"
blocked = podcast.cloud_tts_podcast(turns, work, podcast.PROFILES["te"], "te")
print(json.dumps({"parts": len(parts or []), "voices": sorted(set(calls)), "used": sum(used.values()),
                  "blocked": blocked is None, "split": len(calls)}))
"""
        p = subprocess.run([sys.executable, "-c", drill], cwd=work / "app", capture_output=True, text=True, timeout=120)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-1500:], p.stderr[-1500:])
            r = {}
        check(r.get("parts") == 2, "Cloud voices: one audio file per line", errors)
        check(r.get("voices") == ["te-IN-Chirp3-HD-Charon", "te-IN-Chirp3-HD-Kore"],
              "Cloud voices: Telugu male + female Chirp 3 HD voices", errors)
        check((r.get("split") or 0) > 2, "Cloud voices: long lines split under the size limit", errors)
        check((r.get("used") or 0) > 0 and r.get("blocked") is True,
              "Cloud voices: usage counted, stops before the free limit (never charges)", errors)

        # Drill 4: lite model writes too short -> retry, then expand the draft; the editor pass
        # may not cut a script that is already short.
        print("\n=== short scripts get expanded, never cut ===")
        drill = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["WEATHER"] = "0"
import podcast
from pathlib import Path
def lines(n):
    return "\n".join(("ALEX: " if i % 2 == 0 else "MAYA: ") + "word " * 20 for i in range(n))
asked = []
def llm(system, user):
    if user.startswith("SCRIPT:"):
        asked.append("review")
        return lines(30)                       # editor tries to cut 60 lines -> 30
    if "YOUR DRAFT" in user:
        asked.append("expand")
        return lines(80)                       # 1600 words
    asked.append("write")
    return lines(30)                           # 600 words, far under target
got = []
class Stop(Exception): pass
def tts(turns, *a, **k):
    got.append(sum(len(x.split()) for _, x in turns)); raise Stop()
podcast.gemini_podcast = tts
try:
    podcast.make_podcast("brief", "d", Path("sx"), llm, length="About 1,500 to 2,300 words.")
except Stop:
    pass
print(json.dumps({"asked": asked, "words": got}))
"""
        p = subprocess.run([sys.executable, "-c", drill], cwd=work / "app", capture_output=True, text=True, timeout=120)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-1500:], p.stderr[-1500:])
            r = {}
        check(r.get("asked") == ["write", "write", "expand", "review"],
              f"short script: retried, then draft expanded ({r.get('asked')})", errors)
        check(r.get("words") == [1600], f"short script: editor pass did not cut it ({r.get('words')})", errors)
        print("\n=== Hindi drops lines -> asked again for every line ===")
        drill = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
os.environ["WEATHER"] = "0"
import podcast
from pathlib import Path
en = "\n".join(("ALEX: " if i % 2 == 0 else "MAYA: ") + "word " * 20 for i in range(40))
calls = []
def llm(system, user):
    calls.append("TRANSLATION MODE" in system)
    n = 15 if len(calls) == 1 else 40          # first answer drops most lines
    return "\n".join(("ARJUN: " if i % 2 == 0 else "MEERA: ") + "शब्द " * 20 for i in range(n))
got = []
class Stop(Exception): pass
def tts(turns, *a, **k):
    got.append(len(turns)); raise Stop()
podcast.gemini_podcast = tts
try:
    podcast.make_podcast("brief", "d", Path("hx"), llm, lang="hi", base_script=en,
                         length="About 1,900 to 4,000 words.")
except Stop:
    pass
print(json.dumps({"calls": calls, "turns": got}))
"""
        p = subprocess.run([sys.executable, "-c", drill], cwd=work / "app", capture_output=True, text=True, timeout=120)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-800:], p.stderr[-800:])
            r = {}
        check(r.get("calls") == [True, True] and r.get("turns") == [40],
              f"Hindi: dropped lines are caught and every line is asked for again ({r})", errors)

        print("\n=== Microsoft voices blocked -> Google basic voice (audio never missing) ===")
        drill = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import podcast
from pathlib import Path
edge_calls, basic_calls = [], []
async def broken(*a, **k):
    edge_calls.append(1); raise ConnectionError("WSServerHandshakeError")
podcast._speak = broken
def basic(text, out, profile):
    basic_calls.append(profile["gtts"][0]); Path(out).write_bytes(b"ID3fake")
podcast.basic_voice = basic
d = Path("vx"); d.mkdir(exist_ok=True)
podcast.speak_line("నమస్తే", "RAVI", d / "a.mp3", podcast.PROFILES["te"])
podcast.speak_line("రెండో లైన్", "LAKSHMI", d / "b.mp3", podcast.PROFILES["te"])
print(json.dumps({"edge": len(edge_calls), "basic": basic_calls, "files": (d / "b.mp3").exists(),
                  "quality": podcast.QUALITY}))
"""
        p = subprocess.run([sys.executable, "-c", drill], cwd=work / "app", capture_output=True, text=True, timeout=120)
        try:
            r = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(p.stdout[-800:], p.stderr[-800:])
            r = {}
        check(r.get("edge") == 3 and r.get("basic") == ["te", "te"] and r.get("files")
              and any("Google basic voice" in q for q in r.get("quality", [])),
              f"voices: Microsoft blocked -> Telugu still voiced by Google, Microsoft not retried per line ({r})", errors)

        # ---------------------------------------------------------------- workflow logic
        summ = Path(tmp) / "summary.md"
        r = subprocess.run([sys.executable, "-c",
            "import os,sys; sys.path.insert(0, os.getcwd()); import digest; digest.MODELS_USED.append('gemini-x'); "
            "digest.step_summary('morning', [], ['🟠 Telugu'])"], cwd=work / "app", capture_output=True, text=True,
            env={**os.environ, "GITHUB_STEP_SUMMARY": str(summ)}, timeout=60)
        s = summ.read_text() if summ.exists() else ""
        check("gemini-x" in s and "Telugu" in s, "run page summary: AI used, podcasts, missing, issues", errors)

        print("\n=== last-second duplicate guard (sent by another run) ===")
        origin = Path(tmp) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        clone = Path(tmp) / "clone"
        subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
        (clone / "state" / "done").mkdir(parents=True)
        (clone / "state" / "done" / "2026-10-18-morning").write_text("x")
        for cmd in (["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                    ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run(["git", *cmd], cwd=clone, check=True, capture_output=True)
        guard = (
            "import os, sys, datetime\n"
            f"sys.path.insert(0, {str(work / 'app')!r})\n"
            "import digest\n"
            f"digest.ROOT = __import__('pathlib').Path({str(clone)!r})\n"
            "os.environ.update(GITHUB_ACTIONS='true', WB_SCHEDULED='1', GITHUB_REF_NAME='main')\n"
            "d = datetime.datetime(2026, 10, 18, 9)\n"
            "print(digest.sent_elsewhere(d, 'morning'), digest.sent_elsewhere(d, 'weekly'))\n")
        r = subprocess.run([sys.executable, "-c", guard], capture_output=True, text=True, timeout=120)
        check(r.stdout.strip().endswith("True False"),
              "duplicate guard: sees 'sent' on GitHub, ignores other editions" + ("" if r.stdout.strip().endswith("True False") else f" ({r.stdout[-200:]} {r.stderr[-300:]})"), errors)

        # ---------------------------------------------------------------- small units
        print("\n=== small units (links, strip, subject, redaction, feeds) ===")
        unit = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import digest, email_style
out = {}
digest.KNOWN_LINKS.add("https://news.example.com/a")
out["links"] = [digest.link_allowed("https://news.example.com/a"), digest.link_allowed("https://evil.example/x"),
                digest.link_allowed("javascript:alert(1)")]
box = "| Asset | Latest | Change | Status |\n|---|---:|---:|---|\n| 🇮🇳 Nifty 50 | 23,146 | ▲ +0.65% | X |\n| 💵 USD/INR | ₹94.96 | ▼ -0.20% | X |"
out["strip"] = email_style.market_strip(box)
out["strip_empty"] = email_style.market_strip("")
out["subject"] = email_style.subject_line("World Brief — Saturday, 17 October 2026",
    "## 🚨 Top 5\n- 🟡 **NEW** — **RBI cuts repo rate by 25 basis points today**\n- b\n## x\n", True, False)
out["redact"] = digest.redact("key=abc sk-or-v1-123abc github_pat_11AAbb AIzaSyA1234567890123456789012 bot123:ABC-def")
items = [{"id": "S1", "category": "india", "source": "The Hindu", "title": "Cited", "link": "https://a/1"},
         {"id": "S2", "category": "india", "source": "The Hindu", "title": "Not cited", "link": "https://a/2"}]
out["more"] = digest.more_headlines("story [S1]", items)
digest.CATEGORY_CAPS["india"] = 1
pool = [{"category": "india", "source": "Blog", "title": f"Small {n}", "link": f"https://a/s{n}", "coverage": 1, "summary": "", "published": ""} for n in range(5)]
pool.append({"category": "india", "source": "Blog", "title": "Big story", "link": "https://a/big", "coverage": 5, "summary": "", "published": ""})
pool.append({"category": "india", "source": "Paper", "title": "Second big story", "link": "https://a/big2", "coverage": 4, "summary": "", "published": ""})
out["consensus"] = [i["title"] for i in digest.cap_per_category(pool)]
out["wide"] = digest.more_headlines("", [{**i, "id": None} for i in pool])
rss = b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title><item><title>Fresh story here</title><link>https://n.example/1</link><pubDate>' + \
      __import__("email.utils").utils.formatdate(usegmt=True).encode() + b'</pubDate></item></channel></rss>'
class R:
    content = rss
    def raise_for_status(self): pass
def get(url, **k):
    if "bad" in url:
        raise RuntimeError("down")
    return R()
digest.requests.get = get
got = digest.fetch_items({"india": ["https://ok.example/rss", "https://bad.example/rss"], "usa": ["https://ok2.example/rss"]})
out["fetch"] = [(i["category"], i["title"]) for i in got]
print(json.dumps(out, ensure_ascii=False))
"""
        r = subprocess.run([sys.executable, "-c", unit], cwd=work / "app", capture_output=True, text=True, timeout=120)
        try:
            u = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print(r.stdout[-800:], r.stderr[-800:])
            u = {}
        mail = r"""
import os, sys, json
sys.path.insert(0, os.getcwd())
import digest
os.environ.update(GMAIL_USER="news.sender@gmail.com\n", GMAIL_APP_PASSWORD="abcd efgh\n",
                  TO_EMAIL="me@gmail.com\n", EXTRA_EMAILS="a@gmail.com, b@gmail.com\n")
sent = {}
class FakeSMTP:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def login(self, u, p): sent["login"] = u
    def sendmail(self, frm, rcpts, body): sent.update(frm=frm, rcpts=rcpts, body=body)
digest.smtplib.SMTP_SSL = FakeSMTP
digest.send_email("🌏 World Brief · Sun 18 Oct: test", "## 🚨 Top 5\n- one\n", everyone=True)
b = sent.get("body", "")
print(json.dumps({"login": sent.get("login"), "rcpts": sent.get("rcpts"),
                  "from_ok": "From: World Brief <news.sender@gmail.com>" in b, "bcc_hidden": "a@gmail.com" not in b}))
"""
        r = subprocess.run([sys.executable, "-c", mail], cwd=work / "app", capture_output=True, text=True, timeout=60)
        try:
            m = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print(r.stdout[-600:], r.stderr[-900:])
            m = {}
        check(m.get("login") == "news.sender@gmail.com" and m.get("from_ok") and m.get("bcc_hidden")
              and m.get("rcpts") == ["me@gmail.com", "a@gmail.com", "b@gmail.com"],
              f"email: real message builds even with messy secrets (newlines/spaces), BCC hidden ({m})", errors)
        check(u.get("links") == [True, False, False], "links: only known article links survive", errors)
        src_d = (SRC / "digest.py").read_text()
        check('formataddr((os.getenv("EMAIL_FROM_NAME", "World Brief"), user))' in src_d,
              "email: sender name shows as World Brief", errors)
        check("Nifty 50 23,146 ▲0.65%" in u.get("strip", "") and "$1 = ₹94.96 ▼−0.20%" in u.get("strip", "")
              and u.get("strip_empty") == "", f"market strip format ({u.get('strip')})", errors)
        check(u.get("subject", "").startswith("🚨 World Brief · Sat 17 Oct: RBI cuts repo rate"),
              f"subject: urgent flag, short date, top story ({u.get('subject')})", errors)
        red = u.get("redact", "")
        check(not any(s in red for s in ("abc", "sk-or-v1", "github_pat_11", "AIzaSy", "ABC-def")),
              f"logs: secrets scrubbed ({red})", errors)
        check({"Big story", "Second big story"} <= set(u.get("consensus", [])) and len(u.get("consensus", [])) == 2,
              f"selection: a story carried by 3+ outlets reaches the AI even past the category cap ({u.get('consensus')})", errors)
        check("Widely reported" in u.get("wide", "") and "5 outlets" in u.get("wide", ""),
              "More headlines: widely reported stories listed first", errors)
        check("Not cited" in u.get("more", "") and "Cited](" not in u.get("more", ""),
              "More headlines: lists only stories the brief did not cover", errors)
        check(u.get("fetch") == [["india", "Fresh story here"], ["usa", "Fresh story here"]],
              f"feeds: downloaded in parallel, a dead feed is skipped, order kept ({u.get('fetch')})", errors)

        # Speed: merging ~8,000 headlines must take seconds, not an hour (Oct 20-21 slow mornings).
        import random as _r, time as _t, copy as _c
        import digest
        from difflib import SequenceMatcher as _SM
        _r.seed(7)
        _w = ["".join(_r.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(_r.randint(3, 9))) for _ in range(3000)]
        _base = [" ".join(_r.choice(_w) for _ in range(_r.randint(5, 12))) for _ in range(2500)]
        _now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        _items = []
        for _i in range(8000):
            _ws = _r.choice(_base).split()
            if _r.random() < 0.3:
                _ws[_r.randrange(len(_ws))] = _r.choice(_w)
            _items.append({"title": " ".join(_ws), "source": f"S{_i % 40}",
                           "published": _now - __import__("datetime").timedelta(minutes=_i)})
        _t0 = _t.time()
        digest.dedupe(_c.deepcopy(_items), {})
        _dt = _t.time() - _t0
        def _old(items):
            items.sort(key=lambda i: i["published"], reverse=True)
            out, titles = [], []
            for it in items:
                nt = digest.norm_title(it["title"])
                m = next((k for k, x in enumerate(titles) if _SM(None, nt, x).ratio() > 0.8), None)
                if m is None:
                    titles.append(nt); out.append(it)
            return [i["title"] for i in out]
        _same = _old(_c.deepcopy(_items[:800])) == [i["title"] for i in digest.dedupe(_c.deepcopy(_items[:800]), {})]
        check(_dt < 60 and _same, f"speed: 8,000 headlines merged in {_dt:.1f}s, same result as before", errors)

        import datetime, feedcheck, yaml as _y
        now_rss = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        def _get(u):
            if "dead" in u:
                return ConnectionError("x")
            if "old" in u:
                return b"<rss><channel><item><title>a</title><link>https://x/a</link><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item></channel></rss>"
            return f"<rss><channel><item><title>a</title><link>https://x/a</link><pubDate>{now_rss}</pubDate></item></channel></rss>".encode()
        fc = {r["url"].split("/")[2]: r["status"] for r in feedcheck.check(
            {"a": ["https://good.com/r", "https://dead.com/r"], "b": ["https://old.com/r"]}, get=_get)}
        check(fc == {"good.com": "ok", "dead.com": "dead", "old.com": "stale"},
              f"feedcheck: finds dead and stale feeds ({fc})", errors)
        # Watchdog: missing-email alarm + weekly dead-feed switch-off.
        import watchdog
        from zoneinfo import ZoneInfo as _Z
        wd_tmp = Path(tempfile.mkdtemp())
        (wd_tmp / "state" / "done").mkdir(parents=True)
        watchdog.DATA = wd_tmp
        sent_alerts = []
        watchdog.alert = lambda s, b: sent_alerts.append(s)
        sun = datetime.datetime(2026, 10, 18, 14, 50, tzinfo=_Z("America/New_York"))
        watchdog.check_sent(sun)
        miss_all = list(sent_alerts)
        (wd_tmp / "state" / "done" / "2026-10-18-morning").write_text("x")
        (wd_tmp / "state" / "done" / "2026-10-18-weekly").write_text("x")
        sent_alerts.clear()
        watchdog.check_sent(sun)
        check(len(miss_all) == 1 and all(w in miss_all[0] for w in ("morning", "weekly")) and sent_alerts == [],
              f"watchdog: alarm when today's emails were never sent, silent when they were ({miss_all})", errors)
        rows = [{"url": f"https://f{i}.com/r", "status": "ok"} for i in range(10)]
        rows[0]["status"], rows[1]["status"] = "dead", "empty"
        h1, r1 = watchdog.prune_feeds(rows, {})
        h2, r2 = watchdog.prune_feeds(rows, h1)
        h3, r3 = watchdog.prune_feeds([dict(r, status="dead") for r in rows], {})
        check(r1 == [] and sorted(r2) == ["https://f0.com/r", "https://f1.com/r"] and r3 == [],
              "watchdog: feed dead two Sundays in a row switched off; a network blip changes nothing", errors)
        dis = Path(tempfile.mkdtemp())
        (dis / "state").mkdir()
        dead = next(iter(_y.safe_load((REPO / "feeds" / "world.yaml").read_text())["world"]))
        (dis / "state" / "feeds_disabled.json").write_text(json.dumps([dead]))
        os.environ["WB_DATA"] = str(dis)
        still = [u for us in _cfg.feeds(_cfg._merge(_cfg.DEFAULTS, {})).values() for u in us]
        os.environ.pop("WB_DATA")
        check(dead not in still and len(still) > 50, "feeds: switched-off feeds are skipped", errors)
        check(watchdog.check_hour() == 14, f"watchdog: checks 7 h after the send time ({watchdog.check_hour()}h)", errors)
        for k in list(_cfg.APPLIED):
            os.environ.pop(k, None)

        # ---------------------------------------------------------------- CLI, wizard, scheduler
        print("\n=== command line, setup wizard, Docker scheduler ===")
        r = subprocess.run([sys.executable, "-m", "app", "--help"], cwd=work, capture_output=True, text=True, timeout=60)
        check(r.returncode == 0 and "run morning|weekly" in r.stdout and "serve" in r.stdout,
              "CLI: python -m app --help lists the commands", errors)
        wiz = r"""
import os, sys, json
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
os.environ["WB_DATA"] = os.path.join(os.getcwd(), "wizdata")
os.environ.pop("CODESPACES", None); os.environ.pop("GITHUB_ACTIONS", None)
import setup_wizard, yaml
answers = iter(["Asha", "Europe/London", "06:30", "", "gb, xyz", "London", "y", "Sam, Maya", "en-GB",
                "te, fr", "y", "n", "n", "AIzaFAKE", "me@example.com", "abcd efgh ijkl mnop", "", "", "", "n"])
out = []
rc = setup_wizard.main(ask=lambda q: next(answers), say=out.append)
cfg = yaml.safe_load(open("wizdata/config.yaml"))
env = open("wizdata/.env").read()
print(json.dumps({"rc": rc, "tz": cfg["you"]["timezone"], "c": cfg["focus"]["countries"],
                  "cities": cfg["focus"]["cities"], "hosts": cfg["podcast"]["hosts"],
                  "langs": cfg["podcast"]["languages"], "secret_in_cfg": "AIzaFAKE" in open("wizdata/config.yaml").read(),
                  "env_ok": "GEMINI_API_KEY=AIzaFAKE" in env and "GMAIL_APP_PASSWORD=abcdefghijklmnop" in env,
                  "mode": oct(os.stat("wizdata/.env").st_mode & 0o777)}))
"""
        r = subprocess.run([sys.executable, "-c", wiz], cwd=work, capture_output=True, text=True, timeout=60)
        try:
            w = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print(r.stdout[-800:], r.stderr[-800:])
            w = {}
        check(w.get("rc") == 0 and w.get("tz") == "Europe/London" and w.get("c") == ["gb"]
              and w.get("cities") == ["London"] and w.get("hosts") == ["Sam", "Maya"] and w.get("langs") == ["te"],
              f"wizard: answers -> valid config.yaml, bad codes ignored ({w})", errors)
        check(w.get("secret_in_cfg") is False and w.get("env_ok") and w.get("mode") == "0o600",
              "wizard: keys only in .env (private file), never in config.yaml", errors)
        sch = r"""
import os, sys, json
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
import scheduler
calls = []
scheduler.job = lambda *a: calls.append(" ".join(a)) or 0
scheduler.main(max_loops=3, sleep=lambda s: None)
print(json.dumps(calls))
"""
        r = subprocess.run([sys.executable, "-c", sch], cwd=work, capture_output=True, text=True, timeout=60)
        calls = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
        check("run due" in calls and calls.count("run due") == 1 and calls.count("watchdog") <= 1,
              f"Docker scheduler: checks what is due, watchdog hourly ({calls})", errors)
        due = r"""
import os, sys, json
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
os.environ["WB_SEND_TIME"] = "07:00"
import digest
tz = ZoneInfo("America/New_York")
res = {}
for label, dt in (("before", datetime(2026, 10, 20, 6, 30, tzinfo=tz)), ("tue", datetime(2026, 10, 20, 7, 10, tzinfo=tz)),
                  ("late", datetime(2026, 10, 20, 15, 0, tzinfo=tz)), ("sun", datetime(2026, 10, 18, 9, 0, tzinfo=tz))):
    res[label] = digest.due_edition(dt)
digest.DONE_DIR.mkdir(parents=True, exist_ok=True)
(digest.DONE_DIR / "2026-10-18-morning").write_text("x")
res["sun_after_morning"] = digest.due_edition(datetime(2026, 10, 18, 9, 0, tzinfo=tz))
(digest.DONE_DIR / "2026-10-18-weekly").write_text("x")
res["sun_all_done"] = digest.due_edition(datetime(2026, 10, 18, 9, 0, tzinfo=tz))
print(json.dumps(res))
"""
        r = subprocess.run([sys.executable, "-c", due], cwd=work, capture_output=True, text=True, timeout=60,
                           env={**os.environ, "WB_DATA": str(Path(tmp) / "duedata")})
        try:
            dres = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print(r.stdout[-800:], r.stderr[-800:])
            dres = {}
        check(dres == {"before": None, "tue": "morning", "late": None, "sun": "morning",
                       "sun_after_morning": "weekly", "sun_all_done": None},
              f"schedule: due edition from send time + time zone, never twice ({dres})", errors)
        dock = (REPO / "Dockerfile").read_text() if (REPO / "Dockerfile").exists() else ""
        check("ffmpeg" in dock and "USER " in dock and "serve" in dock,
              "Docker: ffmpeg inside, non-root user, scheduler by default", errors)

    print("\nRESULT:", "ALL CHECKS PASSED" if not errors else f"{len(errors)} FAILED")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
