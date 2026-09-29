"""The Content Security Policy (BUILD-GUIDE Step 16).

The application's own pages get the strict policy in settings (CONTENT_SECURITY_POLICY):
scripts from this origin only. A page of the site is served as it was written, so its policy
also allows exactly what that page itself needs, read from its HTML as served:

* the hash of each inline script it runs (JSON-LD and other data blocks are not run);
* its inline event handlers (onclick="…"), by hash, with 'unsafe-hashes';
* the outside hosts it loads scripts, styles, fonts or images from (a few lab and notes
  pages load Mermaid, Prism, jQuery or Google Fonts);
* for the weather demo, the one API it calls.

MathJax is served by the app (study.services.rewrite_for_origin), so it needs no outside host.
Nothing in the page is changed: the policy is sent as a header beside it.
"""
import base64
import hashlib
import html as htmllib
import re
from functools import lru_cache
from urllib.parse import urlsplit

SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
SRC = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.I)
TYPE = re.compile(r"""\btype\s*=\s*["']([^"']*)["']""", re.I)
RUN_TYPES = {"", "text/javascript", "application/javascript", "module", "text/ecmascript"}
TAG = re.compile(r"<[a-zA-Z][^<>]*>")
HANDLER = re.compile(r"""\son[a-z]+\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
MODULE_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)["'](https://[^"']+)["']""")
STYLESHEET = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']stylesheet["'][^>]*>""", re.I)
HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
IMAGE = re.compile(r"""<(?:img|source)\b[^>]*\bsrc\s*=\s*["'](https?://[^"']+)["']""", re.I)
GOOGLE_FONTS = "https://fonts.googleapis.com"

# Outside APIs a page's own scripts call, which its HTML cannot show.
CONNECT = {
    "data-science/labs/course-7-web/15_weather.html": ["https://api.openweathermap.org"],
    "data-science-major/labs/course-7-web/15_weather.html": ["https://api.openweathermap.org"],
}


def _hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def _origin(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme in ("http", "https") and parts.netloc else None


@lru_cache(maxsize=2048)
def for_page(page_html, page_id=""):
    """What this page adds to the base policy: {directive: [sources]}."""
    scripts, styles, fonts, images, connect = [], [], [], [], list(CONNECT.get(page_id, []))
    runs_handlers = False
    for m in SCRIPT.finditer(page_html):
        attrs, body = m.group(1), m.group(2)
        src = SRC.search(attrs)
        if src:
            if (o := _origin(src.group(1))):
                scripts.append(o)
            continue
        kind = TYPE.search(attrs)
        if (kind.group(1).strip().lower() if kind else "") not in RUN_TYPES:
            continue                                   # JSON-LD and other data: not run
        scripts.append(_hash(body))
        scripts += [o for o in (_origin(u) for u in MODULE_IMPORT.findall(body)) if o]
    # event handlers live in tags outside scripts; take the scripts out first
    for tag in TAG.findall(SCRIPT.sub("", page_html)):
        for dq, sq in HANDLER.findall(tag):
            scripts.append(_hash(htmllib.unescape(dq or sq)))
            runs_handlers = True
    for link in STYLESHEET.findall(page_html):
        href = HREF.search(link)
        if href and (o := _origin(href.group(1))):
            styles.append(o)
            if o == GOOGLE_FONTS:
                fonts.append("https://fonts.gstatic.com")
    images += [o for o in (_origin(u) for u in IMAGE.findall(page_html)) if o]
    if runs_handlers:
        scripts.insert(0, "'unsafe-hashes'")
    out = {"script-src": scripts, "style-src": styles, "font-src": fonts, "img-src": images,
           "connect-src": connect}
    return {k: sorted(set(v), key=v.index) for k, v in out.items() if v}


def attach(response, page_html, page_id=""):
    """Add the page's own needs to the policy the middleware sends with this response."""
    extra = for_page(page_html, page_id)
    if extra:
        response._csp_update = extra
    return response
