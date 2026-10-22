"""Check every free AI key with a tiny request and email a one-line-per-key report.
Run with `python -m app check keys` (or Actions -> Run workflow -> keycheck). Never prints keys."""

from __future__ import annotations

import os

import digest
import podfeed

SYSTEM = "You are a test. Reply with exactly the word OK."
USER = "Say OK."


def check(name: str, fn) -> str:
    try:
        text = fn(SYSTEM, USER)
    except Exception as exc:
        return f"❌ {name}: error ({type(exc).__name__})"
    return f"✅ {name}: working" if text and text.strip() else f"❌ {name}: no answer (key missing or rejected)"


def main() -> None:
    lines = [
        check("Gemini (main brain)", digest.call_gemini) if os.getenv("GEMINI_API_KEY") else "❌ Gemini: GEMINI_API_KEY not set",
        check("Mistral (backup 1)", digest.call_mistral) if os.getenv("MISTRAL_API_KEY") else "⚪ Mistral: MISTRAL_API_KEY not set (optional)",
        check("OpenRouter (backup 2)", digest.call_openrouter) if os.getenv("OPENROUTER_API_KEY") else "⚪ OpenRouter: OPENROUTER_API_KEY not set (optional)",
    ]
    state, days = podfeed.token_status() if podfeed.configured() else ("unknown", None)
    lines.append({"ok": f"✅ Podcast key: working, expires in {days} days" if days is not None else "✅ Podcast key: working",
                  "bad": "❌ Podcast key: rejected, regenerate PODCAST_TOKEN"}.get(state, "⚪ Podcast key: could not check"))
    lines.append("✅ Google Cloud voices: key set" if os.getenv("GOOGLE_TTS_API_KEY")
                 else "⚪ Google Cloud voices: not set (optional; free Microsoft voices are the backup)")
    user, pwd = os.getenv("GMAIL_USER", "").strip(), os.getenv("GMAIL_APP_PASSWORD", "").strip()
    lines.insert(0, "✅ Gmail: set (this email proves it works)" if user and pwd and os.getenv("TO_EMAIL")
                 else "❌ Gmail: GMAIL_USER, GMAIL_APP_PASSWORD and TO_EMAIL are all needed")
    if os.getenv("TELEGRAM_ON") == "1":
        lines.append("✅ Telegram: bot token set" if os.getenv("TELEGRAM_BOT_TOKEN")
                     else "❌ Telegram: enabled in config.yaml but TELEGRAM_BOT_TOKEN not set")
    report = "\n".join(f"- {l}" for l in lines)
    print(report)
    digest.send_email("🔑 World Brief key check", "# 🔑 Key check\n\n" + report + "\n")


if __name__ == "__main__":
    main()
