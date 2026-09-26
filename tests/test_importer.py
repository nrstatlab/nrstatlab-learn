import pytest

from apps.core import importer
from apps.study import pages
from apps.study.services import rewrite_for_origin


def test_every_page_splits_and_reassembles_exactly(source):
    for rel, text in source.pages.items():
        assert pages.assemble(pages.page_fields(text)) == text, rel


def test_every_indexed_page_has_all_four_parts(source):
    for rel in source.indexed:
        parts = pages.split(source.pages[rel])
        assert parts is not None, rel
        assert parts["nav_html"].startswith("<!-- site-nav") and parts["foot_html"].endswith("<!-- /site-foot -->")


def test_a_page_without_markers_is_kept_whole():
    text = "<!DOCTYPE html><html><head><title>Demo</title></head><body>hi</body></html>"
    fields = pages.page_fields(text)
    assert fields["shell"] == {"raw": True} and fields["body_html"] == text and fields["title"] == "Demo"


@pytest.mark.parametrize("stub,url,target", [
    ("which-statistical-test.html", "guides/which-test.html", "guides/which-test.html"),
    ("statistics-major/x/unit1.html", "../../statistics/x/unit1.html#s2", "statistics/x/unit1.html#s2"),
    ("a/b.html", "https://example.org/", "https://example.org/"),
])
def test_stub_targets_resolve(stub, url, target):
    html = f'<meta http-equiv="refresh" content="0; url={url}">'
    assert importer.Source._stub_target(stub, html) == target


@pytest.mark.django_db
def test_import_is_idempotent_and_complete(source):
    counts = importer.write_database(source)
    assert counts == {"created": 0, "updated": 0, "unchanged": len(source.pages), "deleted": 0}
    stored = importer.verify_database(source)
    assert stored["markable units"] == len(source.markable) == 310
    assert stored["courses"] == 56 and stored["exams"] == 5


@pytest.mark.django_db
def test_a_changed_page_is_updated_and_a_count_mismatch_is_refused(source):
    rel = "statistics/sampling-theory/unit2.html"
    changed = importer.Source(root=source.root, pages={**source.pages, rel: source.pages[rel] + "\n"},
                              stubs=source.stubs, indexed=source.indexed, courses=source.courses,
                              markable=source.markable, exams=source.exams)
    assert importer.write_database(changed)["updated"] == 1
    changed.stubs = {**source.stubs, "ghost.html": "index.html"}
    with pytest.raises(importer.ImportError_):
        # A redirect the database does not have: verification must refuse it.
        importer.verify_database(changed)


def test_rewrite_moves_the_site_to_a_new_origin_and_root():
    html = ('<link rel="canonical" href="https://nrstatlab.github.io/planning-for-future/a.html">'
            '<link href="/planning-for-future/assets/x.css">')
    out = rewrite_for_origin(html, origin="https://example.in", base="/")
    assert out == '<link rel="canonical" href="https://example.in/a.html"><link href="/assets/x.css">'
