# AGENTS.md — rules for AI coding agents working on this repo

1. Read `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` before changing code.
2. Flow: context → plan → review plan → implement → validate → update docs. Don't guess; ask
   when docs conflict.
3. Before every push: `python tests/e2e.py` → must print ALL CHECKS PASSED (`ruff check .` recommended).
   Add a check for every new feature.
4. Every change updates the README/docs it affects and `docs/CHANGELOG.md` in the same commit.
5. Never commit secrets, real email addresses, or anyone's personal data. The
   no-personal-data test must pass.
6. Everything must stay free for users (no paid APIs, no card-required services).
7. Never hard-code a country, city, time zone, person or URL — add a config option.
8. The email is the priority: an extra (Telegram, player, podcast) failing must never stop it.
