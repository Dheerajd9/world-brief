"""Find your Telegram channel automatically (no channel ID needed).

Run with `python -m app telegram setup` after adding the bot as an admin of your channel. Reads the bot's recent updates (Telegram
keeps them ~24 h: the "bot was added as admin" event or any post in the channel), picks the
channel/group where the bot is an admin, saves its id to state/telegram_channel.json, posts a
test message there and emails a short confirmation. Never prints the bot token."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

import digest

STATE = digest.DATA / "state" / "telegram_channel.json"


DIAG: list[str] = []


def find_chats(token: str) -> dict[int, str]:
    api = f"https://api.telegram.org/bot{token}"
    me = requests.get(f"{api}/getMe", timeout=30).json()
    who = me.get("result") if isinstance(me.get("result"), dict) else {}
    DIAG.append(f"bot token valid: {bool(me.get('ok'))}" + (f" (@{who.get('username')})" if who else ""))
    info = requests.get(f"{api}/getWebhookInfo", timeout=30).json().get("result")
    hook = info.get("url") if isinstance(info, dict) else None
    if hook:                              # a webhook blocks getUpdates
        requests.post(f"{api}/deleteWebhook", timeout=30)
        DIAG.append("removed an old webhook")
    r = requests.get(f"{api}/getUpdates",
                     params={"allowed_updates": json.dumps(["my_chat_member", "channel_post", "message"])},
                     timeout=30)
    res = r.json().get("result", [])
    kinds = sorted({k for u in res for k in u if k != "update_id"})
    DIAG.append(f"updates seen: {len(res)} ({', '.join(kinds) or 'none'})")
    chats: dict[int, str] = {}
    for u in res:
        for key in ("my_chat_member", "channel_post", "message"):
            chat = (u.get(key) or {}).get("chat") or {}
            if chat.get("type") in ("channel", "supergroup", "group") and chat.get("id"):
                chats[chat["id"]] = chat.get("title", "")
    return chats


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        digest.send_email("📱 Telegram setup", "# 📱 Telegram setup\n\n❌ `TELEGRAM_BOT_TOKEN` is not saved yet.\n")
        return
    try:
        chats = find_chats(token)
    except Exception as exc:
        print(f"getUpdates failed: {type(exc).__name__}")
        chats = {}
    ok = []
    for cid, title in chats.items():
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                          json={"chat_id": cid, "text": "✅ World Brief is connected. Daily news and "
                                "podcasts (English, Telugu, Hindi) will arrive here."})
        if r.status_code == 200:
            ok.append((cid, title))
    if ok:
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps({"id": ok[0][0], "title": ok[0][1]}))
        body = (f"✅ Found **{ok[0][1] or 'your channel'}** and posted a test message there. "
                "Every edition will now also go to this channel.")
    elif chats:
        body = ("❌ Found the channel but the bot can't post. Make the bot an **admin** with "
                "**Post messages** on, then run the Telegram setup again.")
    else:
        body = ("❌ No channel found. Post any message (e.g. `hi`) in the Family News channel, "
                "then run the Telegram setup again (Telegram keeps these events ~24 hours).")
    body += "\n\nDetails: " + "; ".join(DIAG + [f"chats found: {len(chats)}"])
    print(body)
    digest.send_email("📱 Telegram setup", "# 📱 Telegram setup\n\n" + body + "\n")


if __name__ == "__main__":
    main()
