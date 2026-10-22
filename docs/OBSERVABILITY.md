# OBSERVABILITY

- Log lines carry run minutes (`[12m] feeds downloaded`, `[14m] written by …`), so a slow step
  is obvious. Emails/secrets masked.
- GitHub run summary: run time, AI used, podcast length, missing items, quality issues.
- `state/scorecard.json`: per-run numbers (raw items, stories, items to AI, minutes, AI calls).
- Health email (only to `TO_EMAIL`) when an edition went out but quality dropped.
- Watchdog: daily "was it sent?" + Sunday feed report (`logs/feedcheck.txt`).
- Docker: `docker compose logs -f`; same files under `/data/logs`.
