# DESIGN SYSTEM (email, Telegram, podcast player)

_Status: APPROVED_ — keeps the look already proven in the personal edition.

## Email
- Width 640px, system font stack, 16px body, line-height 1.55, white cards on #f5f7fb.
- Section header colours (by topic): Top 5 / urgent #dc2626 · regions #2563eb · AI & tech
  #7c3aed · money #059669 · science #0891b2 · lesson/future #4f46e5 · good news #16a34a.
- Big "▶️ Listen" button near the top; market strip under it (green ▲ / red ▼).
- Every bullet: **bold** 2–4 key words; source names as small links.
- Subject: `🌏 World Brief · Thu 22 Oct: <top story>` (🚨 prefix only when urgent).
- Sender name from config (`email.from_name`, default "World Brief").

## Telegram
One message per edition: podcast audio + ≤1,000-char caption (title + top 5 headlines),
buttons: 📖 Full news (Telegraph Instant View) · ▶️ Play · 📰 Yesterday. Pinned.

## Podcast player (GitHub Pages)
Single `play.html`: big play button, chapters, speed control, works on iPhone. Uses the
user's own Pages URL — no owner name hard-coded.

## Voice & tone of the written brief
Very simple English, short sentences, hard terms explained, neutral on politics, labels
✅ CONFIRMED · 🟡 DEVELOPING · 🔵 PROPOSED · ⚖️ COURT · ⚠️ NOT YET VERIFIED.
