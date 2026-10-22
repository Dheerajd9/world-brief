# TESTING

_Status: APPROVED_

## End-to-end test (`python tests/e2e.py`, needs ffmpeg) — must print ALL CHECKS PASSED
Ported from the personal edition (~190 checks) with fake AI, fake email, fake Telegram:
editions (morning, weekly) · one complete email · podcast + chapters + player · Telegram one
message · slow-AI drill (time caps, backup AI) · Gemini-down drill · run-too-long drill ·
fast dedupe speed (8,000 headlines < 60 s, same result) · duplicate-send guard · watchdog ·
feed self-clean · secrets scrubbed from logs · messy secrets still send.

## New for the public edition
- **Config tests**: defaults = whole world only; every example profile (`examples/*.yaml`) and
  `config.example.yaml` validate; country packs, any-country Google News, city searches and
  focus sections/chapters; clear errors for common mistakes.
- **Wizard test**: scripted answers → expected `config.yaml`; keys only in a private `.env`.
- **Scheduler + schedule test**: Docker loop calls `run due`; due edition from send time and
  time zone, never twice.
- **No-personal-data test**: scans the repo for personal names/emails/repo names and secret
  patterns.
- **Docker smoke test** (release workflow): build the image and run `--help` before publishing.

## CI
`test.yml` on every push/PR: config check → e2e. `docker-publish.yml` on a version tag: tests
again, Docker smoke test, then build multi-arch (amd64 + arm64) and push to `ghcr.io`.
