"""Alert the owner (TO_EMAIL) when a World Brief run fails: by email AND by Telegram (personal chat), so a
Gmail problem can't hide a failure. Never prints secrets."""

import os
import smtplib
from email.mime.text import MIMEText


user, pwd, to = (os.getenv(k, "").strip() for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "TO_EMAIL"))
edition = os.getenv("EDITION", "?")
url = os.getenv("RUN_URL", "")
if edition == "test":
    subject = "⚠️ World Brief code test failed"
    body = ("A code change just failed the automatic end-to-end test (fake news, fake AI). "
            "Check the run log (link below) before the next edition.\n\n"
            f"Run details: {url}\n")
else:
    subject = f"⚠️ World Brief ({edition}) run failed — retrying automatically"
    body = (f"The {edition} World Brief run failed.\n\n"
            "Nothing to do: the next scheduled slot will retry automatically "
            "(for a few hours after your send time).\n\n"
            f"Run details: {url}\n")

if user and pwd and to:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(user, pwd)
            s.sendmail(user, [a.strip() for a in to.split(",") if a.strip()], msg.as_string())
        print("failure alert emailed")
    except Exception as exc:
        print(f"could not email failure alert: {type(exc).__name__}")

token, chat = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
if token and chat:
    try:
        import requests          # imported here: the email above must work even without it
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                          json={"chat_id": chat, "text": f"{subject}\n\n{body}",
                                "disable_web_page_preview": True})
        print("failure alert sent on Telegram" if r.status_code == 200 else
              f"Telegram failure alert: HTTP {r.status_code}")
    except Exception as exc:          # the URL holds the bot token: print only the error type
        print(f"could not send Telegram failure alert: {type(exc).__name__}")
