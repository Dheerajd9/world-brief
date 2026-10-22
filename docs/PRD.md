# PRD — World Brief (public, self-hosted edition)

_Status: APPROVED · Last updated: 22 Oct 2026_

## 1. Problem
People want to know what is going on in the world every morning without reading 20 sites,
without paying for a news app, and without missing important stories. Existing news apps are
noisy, ad-driven, or locked to one country's view.

## 2. Product
A free, fully automatic daily news brief that anyone can run **for themselves**:

- Every morning: **one complete email** — top 5, the full news by region and topic, money
  table, truth check, lesson, "more headlines" — with a **two-host podcast** inside.
- Optional: the same as **one Telegram message** (podcast + headlines + "Full news" button).
- Optional: Sunday **weekly deep-dive**.
- Reads ~200 RSS feeds, merges duplicates, ranks by how many outlets carry a story, and has a
  free AI write the brief using only facts from the feeds (with source links).

It is the engine of a personal World Brief that ran daily for months, with everything personal
removed and every personal choice moved into `config.yaml`.

## 3. Users
| User | Wants | Runs it on |
|---|---|---|
| Non-technical reader | Daily email + podcast, set up once | GitHub (template, free) |
| Tech user / self-hoster | Same, on own machine, private | Docker (home server, Pi, VPS) |
| Families / small groups | One person sets up, others receive | Either; extra recipients in config |

## 4. Goals
1. **Free forever** for the user: free AI tier (Gemini) with free backups, Gmail SMTP, free
   GitHub Actions, free voices. No card anywhere.
2. **5-minute setup** with a wizard (`python setup.py`) and a key check.
3. **Any country, any focus**: regions, cities, topics, time zone, send time, languages and
   podcast hosts all in `config.yaml`.
4. **Never misses an edition**: retries, backup AI, watchdog alarm, self-cleaning feeds.
5. **Private by default**: keys only in GitHub Secrets / `.env`; nothing personal in the repo.

## 5. Non-goals (v1)
- Hosted service / sign-up website / paid plans (see ROADMAP).
- Mobile app.
- Portfolio reports and other personal add-ons.
- Voice cloning (possible later; see ROADMAP).

## 6. Features (v1)
| # | Feature | Template (GitHub) | Docker |
|---|---|---|---|
| F1 | Morning brief email (one, complete) | ✅ | ✅ |
| F2 | Podcast (English; optional extra languages) | ✅ (player on GitHub Pages) | ✅ (attached / Telegram) |
| F3 | Sunday weekly | ✅ | ✅ |
| F4 | Telegram one-message delivery | optional | optional |
| F5 | Breaking-news email alerts | optional, off | optional, off |
| F6 | Watchdog (missing-email alarm, weekly feed self-clean) | ✅ | ✅ |
| F7 | Setup wizard + key check | ✅ | ✅ |
| F8 | `config.yaml` (regions, topics, time, hosts, languages, feeds) | ✅ | ✅ |
| F9 | Automatic end-to-end test on every change | ✅ (CI) | ✅ (image built only if tests pass) |

## 7. Success criteria
- A new user goes from zero to first email in ≤ 15 minutes following the README.
- 30 days of daily editions with zero missed emails on default settings.
- Test suite passes on every push; Docker image builds on every release.
- Nothing personal appears anywhere in the public repo (checked by a test).

## 8. Decided
1. **Default = the whole world.** No country is targeted unless the user asks. The wizard offers
   optional extra focus (suggestions: India, USA, UK, Canada, Australia; any 2-letter code works)
   and optional cities.
2. Repo name: `world-brief`.
3. Podcast language: **English first**. Telugu and Hindi offered as optional extra languages
   (off by default); more languages can be added on request.
