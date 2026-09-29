"""Phase 7, the offline part (BUILD-GUIDE Step 16): MathJax from the app's own copy, the
Content Security Policy, logging, the 500 page, and the backup tooling."""
import logging
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from django.views.defaults import server_error

from apps.core import csp
from apps.study.services import rewrite_for_origin

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db
ROOT = Path(settings.BASE_DIR)
MATHJAX_CDN = "cdn.jsdelivr.net/npm/mathjax"
MATHJAX_PAGE = "statistics/descriptive-statistics/unit3.html"
HANDLER_PAGE = "data-science/labs/course-7-web/13_arrays.html"
INLINE_PAGE = "exams/ugc-net/unit9.html"                       # MathJax set up inline
MERMAID_PAGE = "data-science/problem-solving-c/unit1.html"
FONTS_PAGE = "archive/machine-learning/ml_self_study_notes-single-file.html"


def policy(response):
    """{directive: [sources]} from the response's Content-Security-Policy header."""
    out = {}
    for part in response["Content-Security-Policy"].split(";"):
        name, *sources = part.split()
        out[name] = sources
    return out


# ---------------------------------------------------------------- MathJax, served by the app

def test_no_served_page_names_the_mathjax_cdn(source):
    named = [rel for rel, html in source.pages.items() if MATHJAX_CDN in rewrite_for_origin(html)]
    assert not named, named[:5]
    assert sum("vendor/mathjax/es5/" in rewrite_for_origin(h) for h in source.pages.values()) >= 250


def test_the_vendored_mathjax_has_every_file_the_pages_load(source):
    vendor = ROOT / "static/vendor/mathjax"
    assert (vendor / "LICENSE").exists()
    loaded = {m for h in source.pages.values() for m in re.findall(r"mathjax@3/es5/([\w.-]+\.js)", h)}
    assert loaded == {"tex-mml-chtml.js", "tex-chtml.js"}
    for name in loaded:
        assert (vendor / "es5" / name).stat().st_size > 100_000, name
    # the extensions the pages' own configurations load, and the fonts
    for part in ["input/tex/extensions/noerrors.js", "input/tex/extensions/tagformat.js",
                 "output/chtml/fonts/woff-v2/MathJax_Main-Regular.woff"]:
        assert (vendor / "es5" / part).exists(), part


def test_the_app_pages_load_mathjax_from_the_app(client, learner):
    client.force_login(learner)
    body = client.get("/exams/ugc-net/unit7.html").content.decode()
    tpl = (ROOT / "templates/includes/mathjax.html").read_text()
    assert MATHJAX_CDN not in tpl and "<script>" not in tpl
    assert MATHJAX_CDN not in body


# ---------------------------------------------------------------- the Content Security Policy

def test_an_application_page_gets_the_strict_policy(client):
    p = policy(client.get("/accounts/login/"))
    assert p["script-src"] == ["'self'"]
    assert p["default-src"] == ["'self'"] and p["object-src"] == ["'none'"]
    assert p["frame-ancestors"] == ["'none'"] and p["base-uri"] == ["'self'"]
    assert p["form-action"] == ["'self'", "https://accounts.google.com"]


def test_no_template_has_an_inline_script_or_handler():
    found = []
    for path in (ROOT / "templates").rglob("*.html"):
        text = path.read_text()
        for m in re.finditer(r"<script\b([^>]*)>", text):
            if "src=" not in m.group(1) and "ld+json" not in m.group(1):
                found.append((path.name, m.group(0)))
        found += [(path.name, h) for h in re.findall(r"<[a-z][^>]*\son[a-z]+\s*=", text)]
    assert not found, found


def test_a_site_page_allows_exactly_its_own_inline_scripts(client, source):
    r = client.get("/" + INLINE_PAGE)
    body = r.content.decode()
    p = policy(r)
    assert "'unsafe-inline'" not in p["script-src"]
    assert all(s == "'self'" or s.startswith("'sha256-") for s in p["script-src"]), p["script-src"]
    data_blocks = runs = 0
    for m in csp.SCRIPT.finditer(body):
        attrs, text = m.group(1), m.group(2)
        if csp.SRC.search(attrs):
            continue
        kind = csp.TYPE.search(attrs)
        if kind and kind.group(1).lower() in ("application/ld+json", "application/json"):
            assert csp._hash(text) not in p["script-src"]       # data, never run: not allowed
            data_blocks += 1
        else:
            assert csp._hash(text) in p["script-src"]
            runs += 1
    assert data_blocks and runs


def test_inline_handlers_are_allowed_by_hash_only_where_they_are(client):
    p = policy(client.get("/" + HANDLER_PAGE))
    assert "'unsafe-hashes'" in p["script-src"]
    assert csp._hash("return false") in p["script-src"]           # <form onsubmit="return false">
    assert "'unsafe-hashes'" not in policy(client.get("/" + MATHJAX_PAGE))["script-src"]


def test_outside_libraries_are_allowed_only_on_the_pages_that_load_them(client):
    mermaid = policy(client.get("/" + MERMAID_PAGE))
    assert "https://cdn.jsdelivr.net" in mermaid["script-src"]
    fonts = policy(client.get("/" + FONTS_PAGE))
    assert "https://fonts.googleapis.com" in fonts["style-src"] and "https://fonts.gstatic.com" in fonts["font-src"]
    plain = policy(client.get("/" + MATHJAX_PAGE))
    assert not [s for d in ("script-src", "font-src") for s in plain[d] if s.startswith("https://")]


def test_the_404_page_has_the_policy_too(client):
    r = client.get("/no/such/page.html")
    assert r.status_code == 404 and "Content-Security-Policy" in r


# ---------------------------------------------------------------- logging, the 500 page

def test_a_failed_sign_in_logs_no_password(client, learner, caplog):
    wrong = "not-the-password-9"
    with caplog.at_level(logging.DEBUG):
        client.post("/accounts/login/", {"login": learner.email, "password": wrong})
        client.post("/accounts/login/", {"login": learner.email, "password": PASSWORD})
    assert wrong not in caplog.text and PASSWORD not in caplog.text


def test_the_production_log_goes_to_the_console_only(monkeypatch):
    import importlib
    monkeypatch.setenv("EMAIL_URL", "smtp+tls://ci:ci-only@localhost:587")
    prod = importlib.import_module("config.settings.prod")
    assert set(prod.LOGGING["handlers"]) == {"console"}
    assert prod.LOGGING["handlers"]["console"]["class"] == "logging.StreamHandler"


@override_settings(DEBUG=False)
def test_a_server_error_shows_the_sites_500_page():
    r = server_error(RequestFactory().get("/"))
    assert r.status_code == 500
    assert b"Something went wrong on our side" in r.content and b"GitHub Issues" in r.content


# ---------------------------------------------------------------- backups

def test_data_counts_prints_what_a_restore_must_bring_back(learner, capsys):
    call_command("data_counts")
    out = capsys.readouterr().out
    rows = dict(re.findall(r"^(.+?)\s{2,}(\d+)$", out, re.M))
    assert rows["accounts"] == "1"
    assert int(rows["questions"]) > 900
    for name in ["unit progress", "attempts", "responses", "question events", "syllabus items"]:
        assert name in rows, name


def test_the_database_container_can_write_backups_to_the_laptop():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert '"./backups:/backups"' in compose
    assert "backups/" in (ROOT / ".gitignore").read_text().splitlines()
