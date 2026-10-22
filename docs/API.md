# INTERFACES (CLI, config, external APIs)

_Status: APPROVED_ — there is no web API; these are the contracts.

## CLI
| Command | Does |
|---|---|
| `python setup.py` | wizard → `config.yaml` + `.env` / list of GitHub secrets |
| `python -m app run morning\|weekly [--force]` | build and send an edition now |
| `python -m app run due` | send only what is due now and not sent yet (schedulers call this) |
| `python -m app check keys` | test every key, email a ✅/❌ report |
| `python -m app check feeds` | test every feed, write `logs/feedcheck.txt` |
| `python -m app podcast morning` | remake today's podcast from the sent email |
| `python -m app watchdog` | missing-email check now |
| Docker: `docker compose run --rm world-brief <same args>` | same commands in the container |
| GitHub: Actions → Run workflow → choose command | same commands, no install |

## config.yaml (shape)
```yaml
you:      {name: "Asha", timezone: "Europe/London"}
email:    {from_name: "World Brief", send_time: "07:00", weekly: "sunday"}
focus:
  home_country: uk            # picks feeds/uk.yaml + "UK" section
  home_city: London           # adds a city section + local search feeds
  also_follow: [in, us]       # extra country packs
  topics: [ai, money, science, tech, climate, sports]   # sections on/off + order
podcast:  {enabled: true, hosts: ["Sam", "Maya"], minutes: "15-30", languages: []}
telegram: {enabled: false}
alerts:   {breaking: false}
feeds_extra: []               # any RSS URLs to add
```
Secrets (never in config): `GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `TO_EMAIL`,
optional `EXTRA_EMAILS`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHANNEL_ID`, `PODCAST_TOKEN` (only for a separate player repo).

## External APIs used
Gemini `generateContent` + TTS · Mistral / OpenRouter chat completions · Gmail SMTP SSL 465 ·
Telegram Bot API (`sendAudio`, `sendMessage`, `pinChatMessage`) · Telegraph (`createPage`) ·
RSS over HTTPS · market/weather endpoints already in `markets.py`.
