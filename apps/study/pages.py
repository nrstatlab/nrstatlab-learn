"""A page of the static site, split into the parts its generators mark and put back
together exactly. Pure functions: no database, no settings."""
import hashlib
import html
import re

NAV_OPEN = re.compile(r"<!-- site-nav(?::[^>]*)? -->")
NAV_CLOSE = "<!-- /site-nav -->"
FOOT_OPEN = re.compile(r"<!-- site-foot(?::[^>]*)? -->")
FOOT_CLOSE = "<!-- /site-foot -->"
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')


def split(text: str) -> dict | None:
    """The page in its marked parts, or None if it lacks the markers."""
    h0, h1 = text.find("<head>"), text.find("</head>")
    if h0 < 0 or h1 < h0:
        return None
    nav_open = NAV_OPEN.search(text, h1)
    nav_close = text.find(NAV_CLOSE, nav_open.end()) if nav_open else -1
    foot_open = FOOT_OPEN.search(text, nav_close) if nav_close >= 0 else None
    foot_close = text.find(FOOT_CLOSE, foot_open.end()) if foot_open else -1
    if foot_close < 0:
        return None
    nav_end, foot_end = nav_close + len(NAV_CLOSE), foot_close + len(FOOT_CLOSE)
    return {
        "shell": {"pre": text[: h0 + 6], "mid": text[h1:nav_open.start()], "tail": text[foot_end:]},
        "head_html": text[h0 + 6:h1],
        "nav_html": text[nav_open.start():nav_end],
        "body_html": text[nav_end:foot_open.start()],
        "foot_html": text[foot_open.start():foot_end],
    }


def assemble(page) -> str:
    """The original file from its stored parts. Works on a model or a dict."""
    get = page.get if isinstance(page, dict) else lambda k: getattr(page, k)
    shell = get("shell") or {}
    if shell.get("raw"):
        return get("body_html")
    return (shell["pre"] + get("head_html") + shell["mid"] + get("nav_html")
            + get("body_html") + get("foot_html") + shell["tail"])


def page_fields(text: str) -> dict:
    parts = split(text)
    if parts is None:
        parts = {"shell": {"raw": True}, "head_html": "", "nav_html": "", "body_html": text, "foot_html": ""}
    head = parts["head_html"] if not parts["shell"].get("raw") else text[: text.find("</head>") + 1]
    title = TITLE_RE.search(head)
    desc = DESC_RE.search(head)
    parts.update(
        # stored as text, so a page title with "&amp;" reads "&" wherever the app shows it
        title=html.unescape(re.sub(r"\s+", " ", title.group(1)).strip()) if title else "",
        description=desc.group(1) if desc else "",
        has_math="mathjax" in head.lower(),
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )
    assert assemble(parts) == text, "split/assemble is not exact"

    return parts
