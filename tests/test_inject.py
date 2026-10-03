"""What the application adds to the site's pages (apps/core/inject.py)."""
import json
import re

import pytest

from apps.core import inject
from apps.progress import services as progress
from apps.study.models import Unit

pytestmark = pytest.mark.django_db
ACCOUNT_LINK = re.compile(r'<a class="sitenav-plain sitenav-account" href="([^"]*)">')
STATE = re.compile(r'<script id="nrstat-account" type="application/json">(.*?)</script>', re.S)


def state_of(body):
    [raw] = STATE.findall(body)
    return json.loads(raw)


def test_every_page_with_the_site_bar_has_one_account_link(client, source):
    with_bar = [rel for rel, html in source.pages.items() if inject.NAV in html]
    assert len(with_bar) == 688   # 676, and UGC NET Paper I's 12 pages
    wrong = []
    for rel in with_bar:
        body = client.get("/" + rel).content.decode()
        links = ACCOUNT_LINK.findall(body)
        if links != ["/accounts/login/?next=/" + rel] or body.count(inject.OPEN) != 2:
            wrong.append((rel, links))
    assert not wrong, wrong[:5]


def test_pages_without_the_bar_or_progress_are_untouched(client, source):
    bare = [rel for rel, html in source.pages.items() if inject.NAV not in html and inject.PROGRESS_SCRIPT not in html]
    assert bare
    for rel in bare:
        assert inject.OPEN not in client.get("/" + rel).content.decode(), rel


def test_a_guest_gets_no_account_state(client):
    body = client.get("/statistics/sampling-theory/unit2.html").content.decode()
    assert state_of(body) == {"signed_in": False}
    assert "Sign in</span>" in body
    assert "csrftoken" not in client.cookies and "sessionid" not in client.cookies


def test_learn_js_runs_before_progress_js(client):
    body = client.get("/statistics/sampling-theory/unit2.html").content.decode()
    head = body.split("</head>")[0]
    assert '<script src="/static/learn/learn.js"></script>' in head   # not deferred, not async
    assert re.search(r'<script src="[^"]*assets/progress\.js"[^>]*\bdefer\b', head)


def test_a_learner_gets_their_progress_and_a_link_to_it(client, learner, course_units):
    progress.mark_studied(learner, course_units[0].legacy_path)
    client.force_login(learner)
    body = client.get("/" + course_units[1].legacy_path).content.decode()
    state = state_of(body)
    assert state["signed_in"] is True and state["offer_import"] is True
    assert list(state["done"]) == [course_units[0].legacy_path]
    assert learner.email not in body and "learner" not in state["account"]
    assert ACCOUNT_LINK.findall(body) == ["/me/"] and "My progress</span>" in body
    progress.dismiss_import(learner)
    assert state_of(client.get("/" + course_units[1].legacy_path).content.decode())["offer_import"] is False


def test_the_state_cannot_break_out_of_its_script_tag(client, learner, course_units):
    evil = "statistics/sampling-theory/</script><script>alert(1)</script>.html"
    Unit.objects.create(legacy_path=evil, title="x", body_html="x", content_hash="x", course=course_units[0].course)
    progress.mark_studied(learner, evil)
    client.force_login(learner)
    body = client.get("/index.html").content.decode()
    assert "<script>alert(1)" not in body
    assert evil in state_of(body)["done"]


def test_the_404_page_gets_the_account_link(client):
    r = client.get("/no/such/page.html")
    assert r.status_code == 404 and ACCOUNT_LINK.findall(r.content.decode()) == ["/accounts/login/?next=/no/such/page.html"]


def test_app_pages_carry_the_site_bar_with_root_links(client, learner):
    client.force_login(learner)
    body = client.get("/me/").content.decode()
    nav = body.split('<nav class="sitenav"')[1].split("</nav>")[0]
    hrefs = re.findall(r'href="([^"]*)"', nav)
    assert hrefs and all(h.startswith("/") for h in hrefs), [h for h in hrefs if not h.startswith("/")]
    assert 'aria-current="page"' not in nav
    assert state_of(body)["signed_in"] is True
    assert 'href="/assets/site-base.css"' in body and "sitefoot" in body


def test_strip_removes_exactly_what_inject_added(rf, learner, source):
    request = rf.get("/")
    request.user = learner
    for rel in ["index.html", "statistics/sampling-theory/unit2.html", "404.html"]:
        html = source.pages[rel]
        assert inject.strip(inject.inject(html, request)) == html
