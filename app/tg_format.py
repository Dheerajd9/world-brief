"""The full news on Telegram, the same as the email:

- `telegraph_page()` publishes the whole brief as a free Telegraph article, which Telegram
  opens in Instant View (clean reading page inside the app, no browser, no login).
- `full_messages()` turns the brief into Telegram messages (HTML), one section after another,
  each under Telegram's 4,096-character limit, so the whole news can also be read right in the
  channel and searched later.

Both are free (no keys). Never raise: on any problem they return "" / [] and the run goes on.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser

import markdown
import requests

LIMIT = 3800                 # Telegram allows 4,096; keep a margin for the HTML tags
TELEGRAPH = "https://api.telegra.ph"


def _strip_hidden(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", md)


def _tables_to_lines(md: str) -> str:
    """Markdown tables don't exist in Telegram/Telegraph: turn each row into one line."""
    out, header = [], None
    for line in md.split("\n"):
        if re.match(r"^\s*\|.*\|\s*$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if header is None:
                header = cells
                continue
            label, rest = cells[0], [c for c in cells[1:] if c and c != "—"]
            out.append(f"- **{label}**: " + " · ".join(rest))
        else:
            header = None
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- Telegram messages
def _inline(text: str) -> str:
    """Markdown inline -> Telegram HTML (escape first, then bold / italic / links)."""
    links = []

    def keep(m):
        links.append((m.group(1), m.group(2)))
        return f"\x00{len(links) - 1}\x00"
    text = re.sub(r"\[\[?([^\[\]]+?)\]?\]\((https?://[^)\s]+)\)", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: '<a href="{}">{}</a>'.format(
        html.escape(links[int(m.group(1))][1], quote=True),
        html.escape(links[int(m.group(1))][0], quote=False)), text)


TAGS = [   # tap a tag in Telegram to see every past story on that topic
    (r"Top 5|Top stories", "#Top5"), (r"actually matters", "#MustKnow"),
    (r"🏙️", "#Local"),
    (r"AI|robot", "#AI"), (r"Musk|frontier", "#AI #Tech"), (r"Chips|computing|Future tech", "#Tech"),
    (r"Space", "#Space"), (r"world|World", "#World"), (r"Government|politics", "#Politics"),
    (r"Immigration|migration|visas", "#Immigration"),
    (r"Money|market|Economy|finance|Housing|Business|jobs", "#Money"),
    (r"Energy", "#Energy"),
    (r"Severe weather|disasters", "#Weather"), (r"Science|health|climate", "#Science"),
    (r"Cricket|sports", "#Sports"), (r"Truth", "#FactCheck"), (r"Scams|safety", "#Scams"),
    (r"Future signal", "#FutureSignal"), (r"lesson", "#Lesson"), (r"watch next", "#WatchNext"),
    (r"Good news", "#GoodNews"),
]


def tags_for(heading: str) -> str:
    for pat, tag in TAGS:
        if re.search(pat, heading):
            return tag
    return ""


def _line(line: str) -> str:
    s = line.rstrip()
    if not s.strip():
        return ""
    m = re.match(r"^#{1,2}\s+(.*)", s)
    if m:
        tag = tags_for(m.group(1)) if s.startswith("## ") else ""
        return f"\n<b>{_inline(m.group(1))}</b>" + (f"  {tag}" if tag else "")
    m = re.match(r"^#{3,6}\s+(.*)", s)
    if m:
        return f"<b>{_inline(m.group(1))}</b>"
    m = re.match(r"^(\s*)[-*]\s+(.*)", s)
    if m:
        return ("   ◦ " if len(m.group(1)) >= 2 else "• ") + _inline(m.group(2))
    return _inline(s.strip())


def _sources_as_names(md: str) -> str:
    """[[Reuters]](very-long-google-link) -> (Reuters): keeps who reported it, drops the URL
    (Google News links are ~400 characters each and would triple the number of messages)."""
    md = re.sub(r"(?:\s*\[\[([^\]]+)\]\]\(https?://[^)\s]+\))+",
                lambda m: " (" + ", ".join(re.findall(r"\[\[([^\]]+)\]\]", m.group(0))) + ")", md)
    return re.sub(r"\[([^\[\]]+)\]\((https?://[^)\s]{120,})\)", r"\1", md)


def full_messages(md: str) -> list[str]:
    """Whole brief as Telegram HTML messages: a new message at every section, long sections
    split at line breaks. Every story is kept; long source links become source names, and the
    one-line 'More headlines' list stays in the full article (Instant View) and the email."""
    md = re.split(r"(?m)^## 📰 More headlines", md)[0]
    md = _tables_to_lines(_sources_as_names(_strip_hidden(md)))
    msgs: list[str] = []
    buf: list[str] = []

    def flush():
        if "\n".join(buf).strip():
            msgs.append("\n".join(buf).strip())
        buf.clear()
    for raw in md.split("\n"):
        piece = _line(raw)
        if piece == "" and (not buf or buf[-1] == ""):
            continue
        size = len("\n".join(buf))
        # Pack small sections together; start a new message at a section if this one is
        # already long, or whenever the next line would pass Telegram's limit.
        if (raw.startswith("## ") and size > LIMIT * 0.6) or size + len(piece) + 1 > LIMIT:
            flush()
        if len(piece) > LIMIT:                             # one giant line: hard split
            for k in range(0, len(piece), LIMIT):
                msgs.append(piece[k:k + LIMIT])
            continue
        buf.append(piece)
    flush()
    return [m for m in msgs if m.strip()]


# ---------------------------------------------------------------- Telegraph (Instant View)
ALLOWED = {"a", "aside", "b", "blockquote", "br", "code", "em", "figcaption", "figure", "h3",
           "h4", "hr", "i", "li", "ol", "p", "pre", "s", "strong", "u", "ul"}
RENAME = {"h1": "h3", "h2": "h3", "h3": "h4", "h4": "h4", "h5": "h4", "h6": "h4"}


class _Nodes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED:
            return
        node = {"tag": tag}
        href = dict(attrs).get("href")
        if tag == "a" and href and re.match(r"https?://", href):
            node["attrs"] = {"href": href}
        if tag in ("br", "hr"):
            self.stack[-1].setdefault("children", []).append(node)
            return
        self.stack[-1].setdefault("children", []).append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED or tag in ("br", "hr"):
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data.strip() or (data and self.stack[-1] is not self.root):
            self.stack[-1].setdefault("children", []).append(data)


def telegraph_nodes(md: str, drop_links: bool = False) -> list:
    md = _tables_to_lines(_strip_hidden(md))
    md = re.sub(r"^# .*\n", "", md, count=1)                       # title is the page title
    if drop_links:
        md = re.sub(r"\[\[?([^\[\]]+?)\]?\]\(https?://[^)\s]+\)", r"\1", md)
    body = markdown.markdown(md.replace("&", "&amp;").replace("<", "&lt;"), extensions=["extra"])
    p = _Nodes()
    p.feed(body)
    return p.root.get("children", [])


def _parts(md: str, max_bytes: int = 58000) -> list[str]:
    """Split the brief at section boundaries so each Telegraph page stays under its ~64 KB cap."""
    secs = re.split(r"(?m)^(?=## )", md)
    parts, cur = [], ""
    for s in secs:
        test = cur + s
        if cur and len(json.dumps(telegraph_nodes(test, True), ensure_ascii=False).encode()) > max_bytes:
            parts.append(cur)
            cur = s
        else:
            cur = test
    if cur.strip():
        parts.append(cur)
    return parts


def telegraph_pages(title: str, md: str, author: str = "World Brief") -> list[str]:
    """Publish the whole brief as Telegraph article(s) (Instant View in Telegram); several
    parts on a very long day. Returns the URLs ([] on any problem)."""
    try:
        acc = requests.post(f"{TELEGRAPH}/createAccount", timeout=30,
                            data={"short_name": "WorldBrief", "author_name": author}).json()
        token = acc["result"]["access_token"]
        md = _strip_hidden(md)
        parts = _parts(md)
        urls = []
        for i, part in enumerate(parts, 1):
            name = title if len(parts) == 1 else f"{title} ({i}/{len(parts)})"
            content = json.dumps(telegraph_nodes(part, drop_links=True), ensure_ascii=False)
            r = requests.post(f"{TELEGRAPH}/createPage", timeout=60,
                              data={"access_token": token, "title": name[:256],
                                    "author_name": author, "content": content}).json()
            if not r.get("ok"):
                return urls
            urls.append(r["result"]["url"])
        return urls
    except Exception:
        return []
