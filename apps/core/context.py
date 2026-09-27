"""Template context for the application's own pages (dashboard, sign-in, privacy):
the site's navigation bar and the same head fragment the site's pages get."""
import re

from django.utils.safestring import mark_safe

from apps.study import services as study

from . import inject

_RELATIVE_HREF = re.compile(r'href="(?!https?:|/|#|mailto:)([^"]*)"')


def site_nav(request):
    """The home page's navigation bar, with its links made root-absolute so it works
    at any depth, and the account link added."""
    home = study.find("index.html")
    if home is None or not home.nav_html:
        return ""
    nav = _RELATIVE_HREF.sub(r'href="/\1"', home.nav_html).replace(' aria-current="page"', "")
    return mark_safe(inject._before(nav, inject.NAV_END, inject.nav_fragment(request)))


def site_foot():
    home = study.find("index.html")
    if home is None or not home.foot_html:
        return ""
    return mark_safe(_RELATIVE_HREF.sub(r'href="/\1"', home.foot_html))


def learn(request):
    return {
        "learn_head": lambda: mark_safe(inject.head_fragment(request)),
        "learn_nav": lambda: site_nav(request),
        "learn_foot": site_foot,
    }
