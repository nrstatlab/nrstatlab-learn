"""Exam readiness (BUILD-GUIDE Step 12). The done-when test gives a small exam of known
links, depths and passes, and checks the figure against a hand computation; a second
checks CSIR NET, worked by hand from its map (tools/exams/csirmap.py)."""
import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import Client

from apps.core import syllabus
from apps.examinations import readiness as R
from apps.examinations import services as examinations
from apps.examinations.models import Exam, ExamPaper, ExamTarget, SyllabusItem, SyllabusLink
from apps.progress.models import UnitProgress
from apps.study.models import Unit

pytestmark = pytest.mark.django_db
UGC2 = "exams/ugc-net/unit2.html"
TOP1 = "statistics/theory-of-probability/unit1.html"


def set_status(user, path, status):
    UnitProgress.objects.update_or_create(user=user, unit=Unit.objects.get(legacy_path=path),
                                          defaults={"status": status})


# ---------------------------------------------------------------- the done-when test

@pytest.fixture
def fixture_exam(course_units):
    """Five items of known links:
    A  u1 deep                     u1 passed          -> 1
    B  u2 brief, u1 deep           u1 passed          -> 2 / 3
    C  u3 brief                    u3 only studied    -> 0
    D  a course home page only     nothing to mark    -> not counted
    E  no link                     not taught here    -> not counted
    readiness = (1 + 2/3 + 0) / 3 = 5/9 = 55.6%"""
    u1, u2, u3 = course_units[:3]
    exam = Exam.objects.create(slug="fixture-exam", name="Fixture exam", hub_path="exams/iss/index.html", order=99)
    paper = ExamPaper.objects.create(exam=exam, code="P", title="Part one")
    rows = [("A", "deep", [(u1, "deep")]), ("B", "deep", [(u2, "brief"), (u1, "deep")]),
            ("C", "brief", [(u3, "brief")]), ("D", "deep", [("statistics/sampling-theory/index.html", "deep")]),
            ("E", "missing", [])]
    for n, (code, grade, links) in enumerate(rows):
        item = SyllabusItem.objects.create(exam=exam, paper=paper, code=code, text=f"Line {code}", grade=grade, order=n)
        for target, depth in links:
            unit = target if isinstance(target, Unit) else None
            SyllabusLink.objects.create(item=item, unit=unit, depth=depth,
                                        target_path=unit.legacy_path if unit else target)
    return exam, (u1, u2, u3)


def test_a_fixture_exam_gives_the_hand_computed_readiness(learner, fixture_exam):
    exam, (u1, u2, u3) = fixture_exam
    set_status(learner, u1.legacy_path, "passed")
    set_status(learner, u3.legacy_path, "studied")
    r = examinations.readiness(learner, exam)
    assert r["percent"] == 55.6                      # 5/9, by hand
    percents = {i["code"]: i["percent"] for g in r["groups"] for i in g["items"]}
    assert percents == {"A": 100, "B": 67, "C": 0, "D": None, "E": None}
    assert r["counted"] == 3 and r["items"] == 5
    assert [i.code for i in r["page_only"]] == ["D"] and [i.code for i in r["not_here"]] == ["E"]
    assert (r["units_needed"], r["units_passed"], r["units_studied"]) == (3, 1, 1)


def test_csir_net_with_two_units_passed_is_as_worked_by_hand(learner):
    """csirmap.py: UGC NET Unit II is the only unit link of ten of the 39 counted lines
    (Unit 1 lines 1, 2, 3, 5, 6, 9, 12, 13, 15 and 16), so each scores 1. Theory of
    Probability Unit 1 shares line 2 of Unit 4 with UGC NET Unit I, both deep, so that
    line scores 1/2. (10 + 1/2) / 39 = 26.9%."""
    set_status(learner, UGC2, "passed")
    set_status(learner, TOP1, "passed")
    r = examinations.readiness(learner, Exam.objects.get(slug="csir-net"))
    assert r["counted"] == 39
    assert r["percent"] == 26.9


def test_only_passed_units_count(learner):
    exam = Exam.objects.get(slug="csir-net")
    set_status(learner, UGC2, "studied")
    assert examinations.readiness(learner, exam)["percent"] == 0.0
    set_status(learner, UGC2, "passed")
    assert examinations.readiness(learner, exam)["percent"] == 25.6          # 10 / 39


# ---------------------------------------------------------------- the pure arithmetic

def item(code, links, group="G"):
    return R.Item(code=code, text=code, grade="deep", group=group,
                  links=[R.Link(path=p, depth=d, unit=u, title=p, order=o) for p, d, u, o in links])


def test_a_deep_link_counts_twice_a_brief_one():
    it = item("x", [("a", "brief", True, (0, 0)), ("b", "deep", True, (0, 1))])
    assert R.item_readiness(it, {"b"}) == pytest.approx(2 / 3)
    assert R.item_readiness(it, {"a"}) == pytest.approx(1 / 3)


def test_page_only_and_not_here_items_are_out_of_the_mean():
    items = [item("x", [("a", "deep", True, (0, 0))]), item("page", [("home", "deep", False, ())]), item("none", [])]
    assert R.exam_readiness(items, {"a"}) == 100.0
    out = R.compute(items, {"a": "passed"}, set())
    assert out["counted"] == 1 and len(out["page_only"]) == 1 and len(out["not_here"]) == 1


def test_the_ceiling_counts_every_tested_unit_as_passed():
    items = [item("x", [("a", "deep", True, (0, 0))]), item("y", [("b", "deep", True, (0, 1))])]
    out = R.compute(items, {}, {"a"})
    assert (out["percent"], out["ceiling"], out["units_tested"], out["units_needed"]) == (0.0, 50.0, 1, 2)


def test_the_next_units_serve_the_most_lines_then_follow_course_order():
    items = [item("1", [("late", "deep", True, (5, 0)), ("early", "deep", True, (1, 0))]),
             item("2", [("late", "deep", True, (5, 0))]),
             item("3", [("early2", "deep", True, (1, 1))]),
             item("4", [("done", "deep", True, (0, 0))]),
             item("5", [("waiting", "deep", True, (0, 1))])]
    status = {"done": "passed", "waiting": "studied", "early2": "studied"}
    nxt = R.next_units(items, status, tested={"early", "early2"})
    # late serves two lines; early and early2 one each, in course order; the passed unit
    # is done, and a studied unit without a test ("waiting") has nothing left to do
    assert [u["path"] for u in nxt] == ["late", "early", "early2"]
    assert [u["step"] for u in nxt] == ["Study it; its test is not written yet", "Study it, then take its test",
                                        "Take its test"]


# ---------------------------------------------------------------- the import

def test_the_five_maps_are_stored_at_the_counts_they_hold():
    assert examinations.syllabus_counts() == {
        "ugc-net": {"items": 130, "with a unit": 130, "page only": 0, "not here": 0},
        "csir-net": {"items": 52, "with a unit": 39, "page only": 4, "not here": 9},
        "asrb-net": {"items": 99, "with a unit": 73, "page only": 3, "not here": 23},
        "iss": {"items": 147, "with a unit": 112, "page only": 9, "not here": 26},
        "appsc": {"items": 73, "with a unit": 73, "page only": 0, "not here": 0},
    }


def test_ugc_net_links_are_brief_to_its_own_notes_and_deep_to_a_course():
    links = dict(SyllabusItem.objects.get(exam__slug="ugc-net", code="UI-01").links.values_list("target_path", "depth"))
    assert links == {"exams/ugc-net/unit1.html": "brief", TOP1: "deep"}


def test_every_link_is_a_page_and_a_unit_where_it_can_be(source):
    stored = list(SyllabusLink.objects.values_list("target_path", "unit__legacy_path"))
    assert all(path in source.pages for path, _ in stored)
    assert all((unit == path) == (path in source.markable) for path, unit in stored)
    assert not any(path in source.stubs for path, _ in stored)


def test_an_old_address_is_followed_to_its_unit(source):
    old, new = next((o, n) for o, n in source.stubs.items() if n.split("#")[0] in source.markable)
    resolve = syllabus.Resolver(source.stubs, source.markable)
    assert resolve("", old) == new.split("#")[0]
    assert resolve("exams/iss", "../../" + old) == new.split("#")[0]


def test_importing_again_changes_nothing(source):
    counts = examinations.store_syllabus(source.syllabus)
    assert counts == {"created": 0, "updated": 0, "unchanged": 501, "deleted": 0}


def test_an_item_the_map_drops_is_removed(source):
    groups = [dict(g, items=list(g["items"])) for g in source.syllabus["csir-net"]]
    groups[0]["items"].pop()
    counts = examinations.store_syllabus({"csir-net": groups})
    assert counts["deleted"] == 1 and SyllabusItem.objects.filter(exam__slug="csir-net").count() == 51


def test_the_dry_run_writes_nothing():
    SyllabusItem.objects.all().delete()
    call_command("import_site", "--dry-run", verbosity=0)
    assert SyllabusItem.objects.count() == 0


def test_titles_are_stored_as_text_and_exams_named_as_the_menu_names_them():
    assert not Unit.objects.filter(title__regex=r"&[a-z]+;").exists()
    assert "Real Analysis & Matrix Algebra" in Unit.objects.get(legacy_path=UGC2).title
    assert list(Exam.objects.values_list("name", flat=True)) == [
        "UGC NET Statistics", "CSIR NET Mathematical Sciences", "ASRB NET Agricultural Statistics", "ISS", "APPSC"]


# ---------------------------------------------------------------- the pages

def test_signed_out_visitors_are_sent_to_sign_in(client):
    for url in ("/readiness/", "/readiness/ugc-net/"):
        r = client.get(url)
        assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_the_readiness_page(client, learner):
    set_status(learner, UGC2, "passed")
    client.force_login(learner)
    html = client.get("/readiness/csir-net/").content.decode()
    assert "<b>25.6%</b> ready" in html and "<b>56.4%</b>" in html and "7 of the 23 units" in html
    assert "Not taught on this site yet (9)" in html and "pages with nothing to mark (4)" in html
    assert "Next to study" in html
    assert client.get("/readiness/no-such-exam/").status_code == 404
    listing = client.get("/readiness/").content.decode()
    assert listing.count('class="app-course-title"') == 5


def test_the_target_is_only_ever_your_own(client, make_learner):
    a, b = make_learner("a@example.com"), make_learner("b@example.com")
    client.force_login(a)
    client.post("/readiness/iss/target")
    client.force_login(b)
    client.post("/readiness/csir-net/target")
    client.post("/readiness/iss/target", {"action": "clear"})      # not b's exam: nothing changes
    assert ExamTarget.objects.get(user=a).exam.slug == "iss"
    assert ExamTarget.objects.get(user=b).exam.slug == "csir-net"
    client.post("/readiness/csir-net/target", {"action": "clear"})
    assert not ExamTarget.objects.filter(user=b).exists()


def test_setting_the_target_needs_the_csrf_token(learner):
    c = Client(enforce_csrf_checks=True)
    c.force_login(learner)
    assert c.post("/readiness/iss/target").status_code == 403
    assert not ExamTarget.objects.exists()


def test_the_dashboard_card(client, learner):
    client.force_login(learner)
    assert "Choose the exam you are preparing for" in client.get("/me/").content.decode()
    set_status(learner, UGC2, "passed")
    examinations.set_target(learner, Exam.objects.get(slug="csir-net"))
    html = client.get("/me/").content.decode()
    assert "CSIR NET Mathematical Sciences" in html and "25.6% ready" in html


def test_the_export_includes_the_target(client, learner):
    examinations.set_target(learner, Exam.objects.get(slug="iss"))
    client.force_login(learner)
    data = client.get("/me/export").json()
    assert data["exam_target"] == {"exam": "iss", "exam_date": None}


def test_each_map_page_offers_readiness(client, learner):
    import json
    import re

    def state(path):
        html = client.get("/" + path).content.decode()
        return json.loads(re.search(r'<script id="nrstat-account" type="application/json">(.*?)</script>', html).group(1))

    for slug, pages in syllabus.MAP_PAGES.items():
        for path in pages:
            if not (settings.CONTENT_DIR / path).exists():
                continue  # a map page the content does not publish yet (UGC NET Paper I, until approved)
            r = state(path)["readiness"]
            assert r["url"] == f"/readiness/{slug}/" and r["sign_in"].startswith("/accounts/login/?next=")
    assert "readiness" not in state("exams/appsc/solved-2025-paper-ii.html")
    client.force_login(learner)
    set_status(learner, UGC2, "passed")
    r = state("exams/csir-net/index.html")["readiness"]
    assert (r["percent"], r["ceiling"]) == (25.6, 56.4) and "sign_in" not in r

