# DATA (no database — JSON files)

_Status: APPROVED_

All state is plain JSON under `state/` (template mode: committed to the user's own repo;
Docker: `/data/state`). Nothing is sent anywhere else.

| File | What | Kept |
|---|---|---|
| `state/seen.json` | hashes of headlines already sent | 7 days |
| `state/stories.json` | story ledger (continuing stories, "Previously / New") | rolling |
| `state/entities.json` | people/orgs/places seen recently | rolling |
| `state/beliefs.json` | weekly long-term conclusions | ≤12 |
| `state/trends.json` | topic counters per day | 30 days |
| `state/source_quality.json` | how often each source gets cited | rolling |
| `state/scorecard.json` | per-run stats (items, minutes, AI used) | 60 runs |
| `state/done/<date>-<edition>` | "sent" markers (no duplicates) | 14 days |
| `state/feed_health.json` | bad-Sunday counter per feed | rolling |
| `state/telegram_*.json` | channel id, yesterday's article link | latest |
| `briefs/<date>.md` | archive of each email (memory for tomorrow) | 30 days (configurable) |
| `briefs/podcasts/*.txt` | podcast scripts (memory) | 14 days |

No personal data beyond what the user puts in `config.yaml`; email addresses and keys live
only in secrets / `.env`, never in state files or logs (logs mask addresses).
