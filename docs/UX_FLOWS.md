# UX FLOWS

_Status: APPROVED_

## Flow A — GitHub template (no install, recommended)
1. Open `github.com/<owner>/world-brief` → **Use this template** → create **public** repo
   (public = unlimited free Actions minutes).
2. Get two free keys (README has screenshots): Gemini API key; Gmail app password.
3. Open the repo in GitHub Codespaces (free) or locally → `python setup.py`:
   - your name · email(s) to send to · time zone (auto-detected) · send time (default 7:00)
   - your country + city (picks feed packs and sections) · extra countries to follow
   - podcast on/off · host names · extra languages (optional)
   - Telegram on/off
   → writes `config.yaml`, prints the exact secrets to paste in Settings → Secrets.
4. Commit `config.yaml` → the test run goes green → Actions → **Run workflow → keycheck** →
   ✅/❌ email for every key.
5. Next morning: first email. (Optional: the free cron-job.org timer for on-time delivery.)

## Flow B — Docker
1. `curl -O .../docker-compose.yml && curl -O .../.env.example && cp .env.example .env`
2. `docker compose run --rm world-brief setup` (same wizard, writes into `./data`)
3. `docker compose up -d` → container runs forever; logs: `docker compose logs -f`.
4. Send one now: `docker compose run --rm world-brief run morning`.

## Flow C — Daily reader
Email arrives once, complete: Top 5 → 🎧 Listen button → sections → More headlines.
Telegram (optional): one pinned message with the podcast + 📖 Full news / ▶️ Play buttons.

## Flow D — Something goes wrong
- Run failed → email (+ Telegram) alert; next slot retries automatically.
- Nothing sent by 2 PM → watchdog alert.
- Feeds die → removed automatically after 2 Sundays; report email.
- User changes settings → edit `config.yaml`, commit (or restart container).
