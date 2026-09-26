"""Phase 1 is done when every address of the static site still works (BUILD-GUIDE Step 6):
every indexed page returns 200 with the same content, every old address returns 301."""
import pytest
from django.conf import settings

from apps.study.services import rewrite_for_origin

pytestmark = pytest.mark.django_db


def expected_html(source, rel):
    return rewrite_for_origin(source.pages[rel])


def test_every_indexed_page_is_served_byte_for_byte(client, source):
    wrong = []
    for rel in sorted(source.indexed):
        r = client.get("/" + rel)
        if r.status_code != 200 or r.content.decode() != expected_html(source, rel):
            wrong.append((rel, r.status_code))
    assert not wrong, f"{len(wrong)} of {len(source.indexed)} pages differ, e.g. {wrong[:5]}"
    assert len(source.indexed) == 675


def test_every_other_page_is_still_served(client, source):
    """The lab demos, 404.html and the archive page are not in the sitemap but work today."""
    others = sorted(set(source.pages) - source.indexed)
    wrong = [rel for rel in others if client.get("/" + rel).content.decode() != expected_html(source, rel)]
    assert not wrong, wrong
    assert len(others) == 18


def test_every_old_address_is_a_permanent_redirect_to_a_page(client, source):
    wrong = []
    for old, new in sorted(source.stubs.items()):
        r = client.get("/" + old)
        if r.status_code != 301 or r["Location"] != "/" + new:
            wrong.append((old, r.status_code, r.get("Location")))
            continue
        target = client.get("/" + new.split("#")[0])
        if target.status_code != 200:
            wrong.append((old, "target", target.status_code))
    assert not wrong, f"{len(wrong)} redirects wrong, e.g. {wrong[:5]}"
    assert len(source.stubs) == 946


def test_folders_behave_as_on_github_pages(client, source):
    folders = sorted({rel[: -len("index.html")] for rel in source.pages if rel.endswith("index.html")})
    for folder in folders:
        assert client.get("/" + folder).status_code == 200, folder
        if folder:
            r = client.get("/" + folder.rstrip("/"))
            assert (r.status_code, r["Location"]) == (301, "/" + folder), folder


def test_home_page(client, source):
    assert client.get("/").content.decode() == expected_html(source, "index.html")


def test_unknown_address_gets_the_site_404_page(client):
    r = client.get("/no/such/page.html")
    assert r.status_code == 404
    body = r.content.decode()
    assert "/planning-for-future/" not in body.replace("https://nrstatlab.github.io/planning-for-future/", "")
    assert 'href="/assets/site-base.css"' in body


def test_every_site_file_is_served_at_its_old_path(client, source):
    wrong = []
    for rel in source.site_files:
        r = client.get("/" + rel)
        body = b"".join(r.streaming_content) if r.streaming else r.content
        if r.status_code != 200 or body != (settings.CONTENT_DIR / rel).read_bytes():
            wrong.append((rel, r.status_code))
    assert not wrong, f"{len(wrong)} files wrong, e.g. {wrong[:5]}"


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok", "database": "ok"}
