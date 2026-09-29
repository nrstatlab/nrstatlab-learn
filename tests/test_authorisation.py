"""The authorisation review (BUILD-GUIDE Step 16: "check authorisation on every view that takes
an id"). Every route with a parameter is listed here with how it is protected, and a new one
fails this test until it is added. Then, for each kind:

* an attempt or a sitting is only ever its owner's: signed out, you are sent to sign in;
  signed in as someone else, it does not exist (404);
* a route that takes a unit, a paper or an exam acts only on the signed-in learner's own data,
  and needs sign-in;
* every POST needs the CSRF token;
* the admin is for staff only."""
import pytest
from django.test import Client
from django.urls import URLResolver, get_resolver, reverse

from apps.assessments import engine
from apps.assessments.models import UnitTest
from apps.papers import services as papers
from apps.papers.models import SolvedPaper
from apps.progress import services as progress

pytestmark = pytest.mark.django_db
UNIT = "exams/ugc-net/unit7.html"

OWNER = "only the owner of the attempt or sitting"
SIGNED_IN = "signed in; acts on your own data only"
KEY = "allauth: a one-time key sent by email"
PAGE = "the site's pages, public"
ROUTES = {
    "test_attempt": (OWNER, "GET"), "test_answer": (OWNER, "POST"), "test_submit": (OWNER, "POST"),
    "test_result": (OWNER, "GET"),
    "paper_sitting": (OWNER, "GET"), "paper_answer": (OWNER, "POST"), "paper_check": (OWNER, "POST"),
    "paper_reveal": (OWNER, "POST"), "paper_submit": (OWNER, "POST"), "paper_review": (OWNER, "GET"),
    "test_intro": (SIGNED_IN, "GET"), "test_start": (SIGNED_IN, "POST"),
    "paper_rules": (SIGNED_IN, "GET"), "paper_start": (SIGNED_IN, "POST"),
    "readiness_exam": (SIGNED_IN, "GET"), "readiness_target": (SIGNED_IN, "POST"),
    "account_confirm_email": (KEY, "GET"), "account_reset_password_from_key": (KEY, "GET"),
    None: (PAGE, "GET"),
}
# POST routes with no parameter: each changes only the signed-in learner's own data.
OWN_POSTS = ["progress_studied", "progress_import", "progress_import_dismiss", "account_delete"]


def routes_with_parameters():
    def walk(resolver, prefix=""):
        for p in resolver.url_patterns:
            if isinstance(p, URLResolver):
                if str(p.pattern).startswith("staff/"):
                    continue                     # the admin: tested apart, below
                yield from walk(p, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern), p.name
    return [(pat, name) for pat, name in walk(get_resolver()) if "<" in pat or "(?P" in pat]


def test_every_route_with_a_parameter_is_reviewed():
    missing = [(pat, name) for pat, name in routes_with_parameters() if name not in ROUTES]
    assert not missing, f"not in the authorisation review: {missing}"


@pytest.fixture
def owned(make_learner):
    """Learner A's unit-test attempt and paper sitting, and learner B."""
    a, b = make_learner("a@example.com", "A"), make_learner("b@example.com", "B")
    progress.mark_studied(a, UNIT)
    attempt = engine.start(a, UnitTest.objects.get(unit__legacy_path=UNIT))
    sitting = papers.start(a, SolvedPaper.objects.get(slug="appsc-aso-2025-paper-ii"), papers.EXAM)
    return a, b, {"test": attempt.pk, "paper": sitting.attempt_id}


def owner_urls(ids):
    for name, (kind, method) in ROUTES.items():
        if kind == OWNER:
            yield name, method, reverse(name, args=[ids["test" if name.startswith("test_") else "paper"]])


def test_an_attempt_is_only_ever_its_owners(owned):
    a, b, ids = owned
    anonymous, other, own = Client(), Client(), Client()
    other.force_login(b)
    own.force_login(a)
    for name, method, url in owner_urls(ids):
        call = getattr(anonymous, method.lower())
        r = call(url)
        assert r.status_code == 302 and "/accounts/login/" in r["Location"], (name, r.status_code)
        r = getattr(other, method.lower())(url, {}, content_type="application/json") if method == "POST" else other.get(url)
        assert r.status_code == 404, (name, r.status_code)
    assert own.get(reverse("test_attempt", args=[ids["test"]])).status_code == 200
    assert own.get(reverse("paper_sitting", args=[ids["paper"]])).status_code == 200


def test_routes_that_take_a_unit_paper_or_exam_need_sign_in(owned):
    a, _, _ = owned
    unit_id = UnitTest.objects.get(unit__legacy_path=UNIT).unit_id
    args = {"test_intro": [unit_id], "test_start": [unit_id], "paper_rules": ["appsc-aso-2025-paper-ii"],
            "paper_start": ["appsc-aso-2025-paper-ii"], "readiness_exam": ["iss"], "readiness_target": ["iss"]}
    for name, (kind, method) in ROUTES.items():
        if kind == SIGNED_IN:
            r = getattr(Client(), method.lower())(reverse(name, args=args[name]))
            assert r.status_code == 302 and "/accounts/login/" in r["Location"], name


def test_every_post_needs_the_csrf_token(owned):
    a, _, ids = owned
    c = Client(enforce_csrf_checks=True)
    c.force_login(a)
    unit_id = UnitTest.objects.get(unit__legacy_path=UNIT).unit_id
    urls = [url for _, method, url in owner_urls(ids) if method == "POST"]
    urls += [reverse("test_start", args=[unit_id]), reverse("paper_start", args=["appsc-aso-2025-paper-ii"]),
             reverse("readiness_target", args=["iss"])]
    urls += [reverse(name) for name in OWN_POSTS]
    for url in urls:
        assert c.post(url, {}).status_code == 403, url


def test_the_admin_is_for_staff_only(owned, django_user_model):
    a, _, _ = owned
    learner = Client()
    learner.force_login(a)
    for url in ["/staff/", "/staff/assessments/question/1/change/", "/staff/assessments/reviewquestion/",
                f"/staff/accounts/user/{a.pk}/change/", "/staff/assessments/attempt/"]:
        r = learner.get(url)
        assert r.status_code == 302 and "/staff/login/" in r["Location"], url
