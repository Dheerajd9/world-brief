# DEPLOYMENT

## Template mode (GitHub)
- Repo marked **Template repository**. Workflows read the schedule from `config.yaml`
  (cron slots every 30 min in a window around the send time; the run decides what is due in
  the user's time zone, so no cron editing and DST is automatic).
- Optional on-time timer: cron-job.org → workflow_dispatch API (guide in README).
- Podcast player: GitHub Pages from the generated `podcast` branch (Settings → Pages → Branch: podcast), one click.

## Docker
- `Dockerfile`: python:3.12-slim + ffmpeg, non-root, `ENTRYPOINT ["python","-m","app"]`,
  default command `serve` (scheduler loop).
- `docker-compose.yml`: one service, `env_file: .env`, volume `./data:/data`,
  `restart: unless-stopped`.
- Image: `ghcr.io/<owner>/world-brief:<version>` and `:latest`, linux/amd64 + linux/arm64
  (Raspberry Pi, Apple Silicon). Built by `docker-publish.yml` on tag `v*` after tests pass.

## Releases
Semantic versions. `CHANGELOG.md` updated per release. Template users get updates by a
"Sync from upstream" guide (or GitHub's "Update branch" via a fork-style remote).
