"""What the application adds to a stored page of the site as it serves it.

Two fragments, each between <!-- nrstat-learn --> markers so that removing them
gives back the original page exactly (tests/test_pages.py checks every page):

1. In the navigation bar, as its last item: "Sign in", or "My progress" for a
   signed-in learner.
2. At the end of <head>: the learner's account state as JSON, and learn.js, which
   hands that state to the site's own assets/progress.js (see static/learn/learn.js).
   learn.js is not deferred, so it runs before progress.js whatever their order.

Pages without the site's navigation or progress script (the lab demos) are
served untouched.
"""
import re
from urllib.parse import quote

from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.utils.html import escape, json_script

from apps.accounts import services as accounts
from apps.assessments import services as assessments
from apps.papers import services as papers
from apps.progress import services as progress

OPEN, CLOSE = "<!-- nrstat-learn -->", "<!-- /nrstat-learn -->"
MARKED = re.compile(re.escape(OPEN) + ".*?" + re.escape(CLOSE), re.S)
NAV = '<nav class="sitenav" aria-label="Site">'
NAV_END = "\n  </div>\n</nav>"          # the close of .sitenav-in, then of the bar
HEAD_END = "</head>"
PROGRESS_SCRIPT = "assets/progress.js"
ICON = ('<svg class="sitenav-icon" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>')


def account_state(request, page_id=None):
    """What learn.js needs: whether anyone is signed in, their progress, and, on a unit
    page whose test is open to take, the test (never anything about its answers)."""
    user = request.user
    state = {"signed_in": False}
    if user.is_authenticated:
        state = {
            "signed_in": True,
            "account": accounts.account_marker(user),
            "done": progress.done_map(user),
            "offer_import": accounts.import_offer_open(user),
            "csrf": get_token(request),
        }
    if page_id:
        paper = papers.paper_for_page(page_id)
        if paper:
            r = papers.rules(paper)
            state["paper"] = {"url": f"/papers/{paper.slug}/", "n": r["count"], "minutes": r["duration"],
                              "wrong": str(-r["wrong"]) if r["scheme_recorded"] and r["wrong"] else None}
            if not user.is_authenticated:
                state["paper"]["sign_in"] = "/accounts/login/?next=" + quote(f"/papers/{paper.slug}/", safe="/")
        test = assessments.availability(user, page_id)
        if test["has_test"]:
            state["test"] = test
            if not user.is_authenticated:
                state["test"]["sign_in"] = "/accounts/login/?next=" + quote("/" + page_id, safe="/")
    return state


def head_fragment(request, state=None, page_id=None):
    state = account_state(request, page_id) if state is None else state
    # static() gives the hashed, long-cached names in production.
    return (OPEN + f'<link rel="stylesheet" href="{static("learn/learn.css")}">'
            + json_script(state, "nrstat-account")
            + f'<script src="{static("learn/learn.js")}"></script>' + CLOSE)


def nav_fragment(request):
    if request.user.is_authenticated:
        href, label = "/me/", "My progress"
    else:
        href, label = "/accounts/login/?next=" + quote(request.path, safe="/"), "Sign in"
    return (OPEN + f'\n    <a class="sitenav-plain sitenav-account" href="{escape(href)}">{ICON}'
            f'<span>{label}</span></a>' + CLOSE)


def _before(html, anchor, fragment, start=0):
    i = html.find(anchor, start)
    return html if i < 0 else html[:i] + fragment + html[i:]


def inject(html, request, page_id=None):
    nav_at = html.find(NAV)
    if nav_at < 0 and PROGRESS_SCRIPT not in html:
        return html
    if nav_at >= 0:
        html = _before(html, NAV_END, nav_fragment(request), nav_at)
    return _before(html, HEAD_END, head_fragment(request, page_id=page_id))


def strip(html):
    """The page without what inject() added."""
    return MARKED.sub("", html)
