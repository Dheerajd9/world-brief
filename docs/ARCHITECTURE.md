# ARCHITECTURE

_Status: APPROVED (built in v0.1)_

## 1. One pipeline, two ways to run it

```
            ┌──────────────── config.yaml + secrets (.env / GitHub Secrets) ────────────────┐
            ▼                                                                               │
 ~200 RSS feeds ─► fetch (parallel) ─► merge duplicates (fast, coverage count) ─► rank/cap  │
                                                                                            │
   ─► AI writes brief (Gemini → Mistral → OpenRouter, facts only, [S12] source ids)         │
   ─► fact-check pass ─► link sources ─► podcast script (2 hosts) ─► voices ─► MP3          │
   ─► ONE email (news + podcast) ─► Telegram (one message, optional) ─► save memory ◄───────┘
```

| Runner | Trigger | State storage | Podcast hosting |
|---|---|---|---|
| **GitHub template** | Actions cron + optional cron-job.org timer | committed to the user's repo (`state/`, `briefs/`) | GitHub Pages in the user's repo (or email attachment) |
| **Docker** | built-in scheduler loop in the container | `/data` volume | email attachment + Telegram audio |

The pipeline code is identical; only the trigger differs (workflow vs `scheduler.py`).

## 2. Repo layout (proposed)

```
world-brief/
├─ app/                     # the pipeline (de-personalised from a personal edition)
│  ├─ __main__.py           # CLI: python -m app run|podcast|check|watchdog|alerts|setup|serve
│  ├─ config.py             # loads/validates config.yaml, feed packs, prompt placeholders
│  ├─ digest.py             # orchestration: fetch → dedupe → write → podcast → send → remember
│  ├─ podcast.py podfeed.py languages.py tg_format.py email_style.py markets.py
│  ├─ alerts.py watchdog.py feedcheck.py keycheck.py notify_failure.py tgsetup.py
│  ├─ scheduler.py          # Docker: run what is due, forever
│  ├─ setup_wizard.py       # questions → config.yaml (+ .env)
│  └─ prompts/              # templates with {AUDIENCE} {FOCUS_SECTIONS} {HOST_A} placeholders
├─ config.example.yaml      # every option, commented
├─ feeds/                   # feed packs: world.yaml (always) + country packs (in, us, ca, uk…)
├─ setup.py                 # wizard → config.yaml + .env (or prints GitHub secrets to add)
├─ examples/               # ready-made profiles: world-only, india-usa, uk, canada, australia
├─ Dockerfile  docker-compose.yml  .env.example
├─ .github/workflows/       # brief.yml, watchdog.yml, test.yml, docker-publish.yml
├─ tests/e2e.py             # same end-to-end test (fake AI, fake mail), + no-personal-data check
├─ docs/                    # this folder
└─ LICENSE (MIT)  README.md
```

## 3. Key design choices
- **Config, not code edits**: everything the personal edition hard-coded (time zone, country focus,
  GitHub owner, podcast site, hosts' names, languages, recipients) comes from `config.yaml`.
- **Feed packs**: `feeds/world.yaml` + one pack per chosen country; users can add their own.
- **Prompts take placeholders** filled from config (audience, regions, cities, priorities), so
  a London user gets "UK + London" sections, not India sections.
- **Same safety nets** as the personal version: hard time limit per AI call, backup AIs,
  "one complete email", watchdog, self-cleaning feeds, fast dedupe.
- **No server of ours**: nothing calls home; each user's keys and quotas are their own.

## 4. External services (all free, all the user's own accounts)
Gemini API (required) · Mistral / OpenRouter (optional backups) · Gmail SMTP (required) ·
Telegram Bot API (optional) · GitHub Actions + Pages (template mode) · edge-tts / gTTS voices
(no key) · Open-Meteo, market data endpoints already used by `markets.py` (no key).
