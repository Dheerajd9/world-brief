# ERROR HANDLING

| Failure | What happens | User sees |
|---|---|---|
| One feed down | skipped | nothing (weekly report if it stays dead) |
| Many feeds down (≥10%) | run continues | health alert |
| Gemini busy/slow | 8-min cap per answer, 15-min cap total → Mistral → OpenRouter | nothing, or health note "backup AI" |
| All AI down (1st slot) | slot fails, next slot retries | failure alert |
| All AI down (2nd slot) | headlines-only email | email + health alert |
| Podcast can't start within 2 h | email sent without it | health alert; `podcast morning` remakes it |
| Voice service down | next voice (Gemini → edge-tts → gTTS) | health note if robotic voice used |
| Gmail rejects | run fails | Telegram alert (if set) + next slot retries |
| Two runs at once | concurrency + "done" markers + re-check before send | never a duplicate |
| Nothing ran at all | watchdog at 2 PM local | ⏰ alert |
| Telegram/player fails | logged, email unaffected | health note |
