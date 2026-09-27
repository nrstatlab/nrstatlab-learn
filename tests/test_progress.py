"""Progress on the server (BUILD-GUIDE Step 8): marking, importing browser
progress, the dashboard's summaries, and the endpoints learn.js calls."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts import services as accounts
from apps.progress import services
from apps.progress.models import ActivityEvent, UnitProgress

pytestmark = pytest.mark.django_db
IST = ZoneInfo("Asia/Kolkata")


def status(user, unit):
    row = UnitProgress.objects.filter(user=user, unit=unit).first()
    return row.status if row else "not_started"


# ---------------------------------------------------------------- marking

def test_mark_and_unmark(learner, course_units):
    u = course_units[0]
    assert services.mark_studied(learner, u.legacy_path, True) == "studied"
    assert services.mark_studied(learner, u.legacy_path, True) == "studied"      # idempotent
    assert services.done_map(learner) == {u.legacy_path: timezone.localdate().isoformat()}
    assert services.mark_studied(learner, u.legacy_path, False) == "not_started"
    assert services.mark_studied(learner, u.legacy_path, False) == "not_started"
    assert services.done_map(learner) == {}
    kinds = list(ActivityEvent.objects.filter(user=learner).values_list("kind", flat=True).order_by("at"))
    assert kinds == ["studied", "unstudied"]


def test_studying_becomes_studied(learner, course_units):
    u = course_units[0]
    UnitProgress.objects.create(user=learner, unit=u, status="studying")
    assert services.mark_studied(learner, u.legacy_path, False) == "studying"
    assert services.mark_studied(learner, u.legacy_path, True) == "studied"


def test_a_passed_unit_is_never_changed_by_marking(learner, course_units):
    u = course_units[0]
    UnitProgress.objects.create(user=learner, unit=u, status="passed")
    assert services.mark_studied(learner, u.legacy_path, False) == "passed"
    assert services.mark_studied(learner, u.legacy_path, True) == "passed"
    assert status(learner, u) == "passed"
    assert services.done_map(learner)[u.legacy_path]   # a date: progress.js reads "" as not done


def test_only_units_can_be_marked(learner):
    for page in ["index.html", "statistics/sampling-theory/index.html", "no/such.html", None, 7]:
        with pytest.raises(services.NotAUnit):
            services.mark_studied(learner, page, True)


def test_learners_do_not_see_each_other(make_learner, course_units):
    a, b = make_learner("a@example.com"), make_learner("b@example.com")
    services.mark_studied(a, course_units[0].legacy_path)
    assert services.done_map(b) == {}


# ---------------------------------------------------------------- import

def test_import_brings_over_units_as_studied_and_ignores_the_rest(learner, course_units):
    ids = [u.legacy_path for u in course_units[:2]] + ["index.html", "made/up.html", course_units[0].legacy_path]
    result = services.import_browser(learner, ids)
    assert result == {"imported": 2, "already": 0, "ignored": ["index.html", "made/up.html"]}
    assert all(status(learner, u) == "studied" for u in course_units[:2])
    assert UnitProgress.objects.filter(user=learner, source="browser_import").count() == 2
    assert not accounts.import_offer_open(learner)


def test_import_never_lowers_a_status_or_passes_a_unit(learner, course_units):
    UnitProgress.objects.create(user=learner, unit=course_units[0], status="passed")
    UnitProgress.objects.create(user=learner, unit=course_units[1], status="studied")
    result = services.import_browser(learner, [u.legacy_path for u in course_units[:3]])
    assert (result["imported"], result["already"]) == (1, 2)
    assert [status(learner, u) for u in course_units[:3]] == ["passed", "studied", "studied"]
    assert not UnitProgress.objects.filter(user=learner, status="passed").exclude(unit=course_units[0]).exists()


@pytest.mark.parametrize("bad", [None, "a.html", {"a": 1}, ["x.html"] * 401, ["x" * 301], [""], [3]])
def test_import_rejects_malformed_lists(learner, bad):
    with pytest.raises(ValueError):
        services.import_browser(learner, bad)
    assert accounts.import_offer_open(learner)


def test_import_accepts_the_largest_allowed_list(learner, course_units):
    ids = [course_units[0].legacy_path] + [f"p/{i}.html" for i in range(399)]
    assert services.import_browser(learner, ids)["imported"] == 1


def test_not_now_closes_the_offer_without_importing(learner):
    assert accounts.import_offer_open(learner)
    services.dismiss_import(learner)
    assert not accounts.import_offer_open(learner)
    assert not UnitProgress.objects.filter(user=learner).exists()


# ---------------------------------------------------------------- summaries

def test_course_summaries(learner, course_units):
    services.mark_studied(learner, course_units[0].legacy_path)
    UnitProgress.objects.create(user=learner, unit=course_units[1], status="passed")
    [summary] = services.course_summaries(learner)
    assert summary["title"] == course_units[0].course.title
    assert summary["path"] == "statistics/sampling-theory/index.html"
    assert (summary["studied"], summary["passed"], summary["total"]) == (2, 1, len(course_units))
    assert summary["percent"] == round(200 / len(course_units))


def _studied_on(user, unit, day, hour=12):
    e = ActivityEvent.objects.create(user=user, kind="studied", unit=unit)
    ActivityEvent.objects.filter(pk=e.pk).update(at=datetime(day.year, day.month, day.day, hour, tzinfo=IST))


def test_streak_counts_consecutive_days_in_india(learner, course_units):
    today = date(2026, 9, 27)
    u = course_units[0]
    assert services.streak(learner, today) == 0
    for back in (0, 1, 2, 4):
        _studied_on(learner, u, today - timedelta(days=back))
    assert services.streak(learner, today) == 3
    # Yesterday's run still counts before today's first unit.
    assert services.streak(learner, today + timedelta(days=1)) == 3
    assert services.streak(learner, today + timedelta(days=2)) == 0
    # 00:30 in India is still the previous day in UTC; it counts as the Indian day.
    _studied_on(learner, u, today - timedelta(days=3), hour=0)
    assert services.streak(learner, today) == 5


def test_last_studied_and_next_unit(learner, course_units):
    assert services.last_studied(learner) == (None, None)
    services.mark_studied(learner, course_units[1].legacy_path)
    services.mark_studied(learner, course_units[0].legacy_path)
    last, nxt = services.last_studied(learner)
    assert last["path"] == course_units[0].legacy_path
    assert nxt["path"] == course_units[2].legacy_path   # unit 2 is done already


# ---------------------------------------------------------------- endpoints

def post(client, url, data, **extra):
    return client.post(url, data if isinstance(data, str) else json.dumps(data),
                       content_type="application/json", **extra)


def test_endpoints_need_a_signed_in_learner(client, course_units):
    for url in ["/me/progress/studied", "/me/progress/import", "/me/progress/import/dismiss"]:
        r = post(client, url, {"page": course_units[0].legacy_path})
        assert r.status_code == 403 and "error" in r.json()
    assert client.get("/me/").status_code == 302


def test_studied_endpoint(client, learner, course_units):
    client.force_login(learner)
    page = course_units[0].legacy_path
    r = post(client, "/me/progress/studied", {"page": page, "done": True})
    assert r.json() == {"page": page, "status": "studied", "done": True}
    r = post(client, "/me/progress/studied", {"page": page, "done": False})
    assert r.json() == {"page": page, "status": "not_started", "done": False}
    assert post(client, "/me/progress/studied", "{not json").status_code == 400
    assert post(client, "/me/progress/studied", {"page": page, "done": "yes"}).status_code == 400
    assert post(client, "/me/progress/studied", ["a"]).status_code == 400
    assert post(client, "/me/progress/studied", {"page": "index.html"}).status_code == 404
    assert client.get("/me/progress/studied").status_code == 405


def test_studied_endpoint_reports_a_passed_unit_as_done(client, learner, course_units):
    client.force_login(learner)
    UnitProgress.objects.create(user=learner, unit=course_units[0], status="passed")
    r = post(client, "/me/progress/studied", {"page": course_units[0].legacy_path, "done": False})
    assert r.json()["status"] == "passed" and r.json()["done"] is True


def test_import_endpoints(client, learner, course_units):
    client.force_login(learner)
    assert post(client, "/me/progress/import", {"done": "x"}).status_code == 400
    r = post(client, "/me/progress/import", {"done": [course_units[0].legacy_path, "nope.html"]})
    assert r.json() == {"imported": 1, "already": 0, "ignored": ["nope.html"]}
    assert post(client, "/me/progress/import/dismiss", {}).json() == {"ok": True}


def test_endpoints_enforce_csrf(learner, course_units):
    client = Client(enforce_csrf_checks=True)
    client.force_login(learner)
    body = {"page": course_units[0].legacy_path, "done": True}
    assert post(client, "/me/progress/studied", body).status_code == 403
    assert status(learner, course_units[0]) == "not_started"
    page = client.get("/" + course_units[0].legacy_path).content.decode()
    token = json.loads(page.split('id="nrstat-account" type="application/json">')[1].split("</script>")[0])["csrf"]
    assert post(client, "/me/progress/studied", body, HTTP_X_CSRFTOKEN=token).status_code == 200
    assert status(learner, course_units[0]) == "studied"


def test_dashboard(client, learner, course_units):
    client.force_login(learner)
    body = client.get("/me/").content.decode()
    assert "Hello, Asha" in body and "Nothing marked done yet" in body
    services.mark_studied(learner, course_units[0].legacy_path)
    body = client.get("/me/").content.decode()
    assert course_units[0].course.title in body
    assert f"1 of {len(course_units)} units done" in body
    assert "1 day in a row" in body
    assert f'href="/{course_units[1].legacy_path}"' in body
    assert 'class="sitenav-plain sitenav-account" href="/me/"' in body
