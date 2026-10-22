# ENVIRONMENT

| Variable / secret | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | writes the brief + podcast voices (free key, aistudio.google.com) |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD` | yes | sends the email (app password, 2-step on) |
| `TO_EMAIL` | yes | main recipient (also gets health alerts) |
| `EXTRA_EMAILS` | no | comma list, receive the brief only (BCC) |
| `MISTRAL_API_KEY`, `OPENROUTER_API_KEY` | no | free backup AIs |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` | no | Telegram delivery |
| `TELEGRAM_CHAT_ID` | no | private alerts only |
| `PODCAST_REPO`, `PODCAST_TOKEN` | no | separate player/feed repo (default: same repo Pages) |
| `WB_SEND_BY_MIN` (120), `WB_AI_CALL_MAX_MIN` (8), `WB_GEMINI_MAX_MIN` (15) | no | time limits |

Local dev: Python 3.12, ffmpeg, `pip install -r requirements.txt`, `cp .env.example .env`.
Docker: everything included; mount `./data:/data`.
