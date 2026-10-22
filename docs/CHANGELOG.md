# CHANGELOG

## v0.1.0 — 2026-10-22
First public release.
- De-personalised engine: whole-world brief by default; optional countries/cities in
  `config.yaml` (own sections, feed packs, market rows, podcast chapters).
- Feed packs: `feeds/world.yaml` (~100 feeds) + India, USA, UK, Canada, Australia; any other
  country via Google News; city searches; `feeds_extra`.
- Setup wizard (`python setup.py`), config validation with clear errors, example profiles.
- CLI `python -m app ...` (run, podcast, check keys/feeds, watchdog, alerts, telegram setup, serve).
- GitHub template workflow (every 30 min, sends what is due in your time zone; DST automatic),
  podcast site on its own `podcast` branch (GitHub Pages).
- Docker image (multi-arch) with a built-in scheduler; state in `/data`.
- Proven safety nets: one complete email, hard AI time limits + backup AIs, fast duplicate
  merging, watchdog alarm, weekly dead-feed switch-off.
- End-to-end test (~166 checks) incl. no-personal-data, wizard, scheduler, schedule logic.
- Docs set: PRD, architecture, flows, design, data, interfaces, security, style, testing,
  agents, environment, errors, deployment, observability, decisions, roadmap.
