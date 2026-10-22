"""Look of the daily email: easy to scan on a phone, nothing left out.

- Subject line shows the top stories, so the news is visible in the inbox.
- "Top 5" in a highlighted box, Telugu + Hindi headlines for family, big ▶️ play buttons.
- One-line market strip (green ▲ / red ▼) under the play buttons.
- Every story is a card; every section has its own colour and a read time.
- Source links become small grey chips; "More headlines" stays compact.
Only presentation changes here: every word of the brief is kept.
"""

from __future__ import annotations

import re

FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# (heading pattern, accent colour)
SECTIONS = [
    (r"Top 5|Top stories", "#d97706"),
    (r"Listen", "#2563eb"),
    (r"తెలుగు|हिंदी", "#7c3aed"),
    (r"Scams|safety", "#dc2626"),
    (r"Good news|Cricket|sports", "#16a34a"),
    (r"Severe weather|disasters", "#0891b2"),
    (r"Students|visas|Travel", "#0369a1"),
    (r"NRI", "#b45309"),
    (r"actually matters", "#059669"),
    (r"🏙️", "#ea580c"),
    (r"🇺🇸|USA", "#1d4ed8"),
    (r"🇮🇳|India", "#f97316"),
    (r"🇨🇦|Canada", "#dc2626"),
    (r"AI|robot|Musk|frontier|Chips|Future tech|Space|🧬|🛰️", "#7c3aed"),
    (r"World|world|🌍|🌎|🗺️", "#0d9488"),
    (r"Government|politics", "#475569"),
    (r"Money|market|Economy|finance|Housing|Business|jobs|Energy", "#b45309"),
    (r"Immigration", "#0369a1"),
    (r"Science|health|climate", "#16a34a"),
    (r"Truth", "#be123c"),
    (r"Future signal|lesson|watch|On this day", "#4f46e5"),
    (r"More headlines", "#6b7280"),
]
BUTTON = {"🔵": "#2563eb", "🟠": "#ea580c", "🟢": "#16a34a"}


def _color(heading: str) -> str:
    for pat, col in SECTIONS:
        if re.search(pat, heading):
            return col
    return "#334155"


def _clean_headline(h: str) -> str:
    h = re.sub(r"^[^\w₹$]*\s*(NEW|UPDATE|PROPOSED|CONFIRMED|DEVELOPING|BREAKING|IN EFFECT)?\s*[—–-]\s*",
               "", h).strip()
    return re.sub(r"\s+", " ", h)


def subject_line(title: str, md: str, urgent: bool, audio: bool) -> str:
    """'🌏 World Brief — Fri, 16 Oct: Rogue AI agents breach… · Taiwan plans $4B… 🎧'"""
    sec = re.search(r"^##[^\n]*Top[^\n]*\n(.*?)(?=^## )", md, re.S | re.M)
    heads = re.findall(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", sec.group(1) if sec else "", re.M)
    short = []
    for h in heads[:3]:
        h = _clean_headline(re.sub(r"\[\[[^\]]+\]\]\([^)]+\)|[*_#`]", "", h))
        if len(h) > 48:
            h = h[:48].rsplit(" ", 1)[0] + "…"
        if h:
            short.append(h)
    day = re.sub(r"^[^—–-]*[—–-]\s*", "", title).strip()
    day = re.sub(r"^(\w{3})\w*,?\s+(\d{1,2})\s+(\w{3})\w*\s+\d{4}$", r"\1 \2 \3", day)
    base = re.sub(r"\s*[—–-].*$", "", title).strip()
    subj = (("🚨 " if urgent else "🌏 ") + base + (f" · {day}" if day and day != title else "")
            + (": " + " · ".join(short) if short else "") + (" 🎧" if audio else ""))
    return re.sub(r"[\r\n]+", " ", subj)[:230]


PICK = ["S&P 500", "Nasdaq", "Euro Stoxx", "Nikkei", "FTSE 100", "Nifty 50", "S&P/TSX", "ASX 200",
        "Gold world ($/troy ounce)", "Brent", "Bitcoin", "USD/INR"]
SHORT = {"Gold world ($/troy ounce)": "Gold/oz", "Brent": "Brent", "USD/INR": "$1 ="}


def market_strip(box_md: str) -> str:
    """One line with the key numbers from the money table (empty if no table)."""
    rows = {}
    for line in box_md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[1] and not set(cells[1]) <= set("-:"):
            rows[cells[0]] = (cells[1], cells[2])
    out = []
    for want in PICK:
        hit = next(((k, v) for k, v in rows.items() if want in k), None)
        if not hit:
            continue
        label = SHORT.get(want, want)
        val, chg = hit[1]
        chg = re.sub(r"\s+", "", chg) if chg and chg != "—" else ""
        chg = chg.replace("+", "").replace("-", "−")
        out.append(f"{label} {val}" + (f" {chg}" if chg else ""))
    return ("**📈 Markets now:** " + " · ".join(out[:7])) if out else ""


def insert_after(md: str, heading_pat: str, block: str) -> str:
    """Put `block` right after the section whose ## heading matches (before the next ##)."""
    if not block:
        return md
    m = re.search(rf"(?m)^## [^\n]*(?:{heading_pat})[^\n]*$", md)
    if not m:
        return md
    nxt = re.search(r"(?m)^## ", md[m.end():])
    pos = m.end() + nxt.start() if nxt else len(md)
    return md[:pos].rstrip() + "\n\n" + block.strip() + "\n\n" + md[pos:]


def _arrows(h: str) -> str:
    h = h.replace("▲", '<span style="color:#16a34a">▲</span>')
    return h.replace("▼", '<span style="color:#dc2626">▼</span>')


def _chips(h: str) -> str:
    """<a>[Reuters]</a> -> small grey source chip."""
    return re.sub(
        r'<a href="([^"]+)">\[([^\]<]{1,40})\]</a>',
        lambda m: (f'<a href="{m.group(1)}" style="display:inline-block;font-size:12px;color:#555;'
                   f'background:#f1f3f5;border-radius:10px;padding:1px 7px;margin:2px 2px 0 0;'
                   f'text-decoration:none">{m.group(2)}</a>'), h)


def _section(part: str) -> str:
    m = re.match(r"<h2>(.*?)</h2>", part, re.S)
    if not m:
        return part
    head, rest = m.group(1), part[m.end():]
    plain = re.sub(r"<[^>]+>", "", head)
    col = _color(plain)
    words = len(re.sub(r"<[^>]+>", " ", rest).split())
    mins = round(words / 200)
    rt = (f' <span style="font-size:13px;font-weight:normal;color:#6b7280">· {mins} min read</span>'
          if mins >= 1 and not re.search(r"More headlines|Listen|తెలుగు|हिंदी", plain) else "")
    h2 = (f'<h2 style="font-size:20px;margin:28px 0 10px;padding:8px 12px;border-left:6px solid {col};'
          f'background:{col}14;border-radius:4px;color:#111">{head}{rt}</h2>')

    if re.search(r"Top 5|Top stories", plain):
        rest = rest.replace("<ul>", '<ul style="padding-left:20px;margin:6px 0">')
        rest = rest.replace("<li>", '<li style="margin:0 0 10px">')
        return (f'<div style="background:#fff7e6;border:1px solid #f5c26b;border-radius:10px;'
                f'padding:4px 14px 8px;margin:16px 0">{h2}{rest}</div>')
    if "Listen" in plain:
        def button(a):
            href, text = a.group(1), a.group(2)
            colr = next((c for k, c in BUTTON.items() if k in text), "#2563eb")
            return (f'<a href="{href}" style="display:block;background:{colr};color:#fff;'
                    f'font-weight:bold;text-decoration:none;padding:11px 16px;border-radius:24px;'
                    f'margin:8px 0;text-align:center">{text}</a>')
        rest = re.sub(r'<a href="([^"]+)">([^<]*▶️[^<]*)</a>', button, rest)
        return (f'<div style="background:#eef4ff;border-radius:10px;padding:4px 14px 10px;'
                f'margin:16px 0">{h2}{rest}</div>')
    if re.search(r"తెలుగు|हिंदी", plain):
        rest = rest.replace("<li>", '<li style="margin:0 0 6px">')
        return (f'<div style="background:#f5f3ff;border-radius:10px;padding:2px 14px 8px;'
                f'margin:12px 0">{h2}{rest}</div>')
    if "More headlines" in plain:
        rest = rest.replace("<li>", '<li style="margin:0 0 4px;font-size:15px">')
        return h2 + rest
    # Story cards: every bullet and every numbered story (### ...) is its own card.
    card = (f'background:#fafafa;border-left:4px solid {col};border-radius:6px;'
            f'padding:10px 12px;margin:10px 0;list-style:none')
    rest = rest.replace("<ul>", '<ul style="padding-left:0;margin:0">')
    rest = rest.replace("<li>", f'<li style="{card}">')
    chunks = re.split(r"(?=<h3>)", rest)
    out = [chunks[0]]
    for ch in chunks[1:]:
        ch = re.sub(r"<h3>(.*?)</h3>", r'<div style="font-weight:bold;font-size:18px;margin:0 0 6px">\1</div>',
                    ch, count=1, flags=re.S)
        out.append(f'<div style="{card}">{ch}</div>')
    return h2 + "".join(out)


def page(body_html: str) -> str:
    """Wrap the converted brief in the styled email page."""
    body_html = _arrows(_chips(body_html))
    parts = re.split(r"(?=<h2>)", body_html)
    first = parts[0]
    first = first.replace("<h1>", f'<h1 style="font-size:26px;margin:8px 0 6px;color:#111">', 1)
    styled = first + "".join(_section(p) for p in parts[1:])
    styled = (styled
              .replace("<table>", '<table style="border-collapse:collapse;width:100%;font-size:14px">')
              .replace("<td", '<td style="border-bottom:1px solid #eee;padding:5px 8px"')
              .replace("<th", '<th style="border-bottom:2px solid #ccc;padding:5px 8px;text-align:left"'))
    footer = ('<p style="margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;'
              'font-size:14px;color:#6b7280">💬 Reply to this email to say what you liked or '
              'what is missing. Every story links to its source.</p>')
    return (f'<html><body style="margin:0;padding:0"><div style="font-family:{FONT};'
            f'max-width:680px;margin:auto;padding:14px;font-size:17px;line-height:1.6;'
            f'color:#1f2328">{styled}{footer}</div></body></html>')

