"""The learner's journey in a real browser (Chromium, through pytest-playwright), on a
live server: progress kept in the browser as a guest, brought over on sign-in, saved
to the account as it is marked, the same on a second device, and the guest's own
progress back after signing out."""
import json
import os

import pytest
from django.core.management import call_command

from apps.progress.models import UnitProgress
from apps.study.models import Unit

from .conftest import PASSWORD

# Playwright's sync API runs an event loop in this thread; the ORM calls made here
# between browser steps are ordinary blocking calls and safe.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]
COURSE = "statistics/sampling-theory"
KEY = "nrstatlab.progress.v1"
TOGGLE = ".progress-toggle button"


@pytest.fixture
def site(live_server):
    """The live server needs committed data, and each test here ends with the
    database emptied, so the site is imported again for each."""
    if not Unit.objects.exists():
        call_command("import_site", verbosity=0)
    return live_server.url


@pytest.fixture
def units(site):
    return list(Unit.objects.filter(course__path=COURSE).order_by("order").values_list("legacy_path", flat=True))


def stored(page):
    return page.evaluate(f"() => JSON.parse(localStorage.getItem('{KEY}') || 'null')")


def statuses(user):
    return dict(UnitProgress.objects.filter(user=user).values_list("unit__legacy_path", "status"))


def mark(page, expect_saved=True):
    """Press the first "Mark this unit done" and wait for the account to answer."""
    if expect_saved:
        with page.expect_response(lambda r: r.url.endswith("/me/progress/studied")) as resp:
            page.locator(TOGGLE).first.click()
        assert resp.value.ok
    else:
        page.locator(TOGGLE).first.click()


def sign_in(page, site, email, next_path):
    page.goto(f"{site}/{next_path}")
    page.locator("a.sitenav-account").click()
    page.fill("input[name=login]", email)
    page.fill("input[name=password]", PASSWORD)
    page.locator("form button[type=submit]").click()
    page.wait_for_url(f"{site}/{next_path}")


def test_a_guest_keeps_progress_in_the_browser_only(page, site, units, learner):
    page.goto(f"{site}/{units[0]}")
    assert page.locator(TOGGLE).first.inner_text() == "Mark this unit done"
    mark(page, expect_saved=False)
    assert page.locator(TOGGLE).first.inner_text() == "Done ✓ (undo)"
    assert list(stored(page)["done"]) == [units[0]]
    assert not UnitProgress.objects.exists()
    assert page.evaluate("() => localStorage.getItem('nrstatlab.account')") is None
    assert page.locator("a.sitenav-account").get_attribute("href") == f"/accounts/login/?next=/{units[0]}"


def test_the_whole_journey(browser, page, site, units, learner):
    # A guest marks two units in this browser.
    for u in units[:2]:
        page.goto(f"{site}/{u}")
        mark(page, expect_saved=False)
    guest = stored(page)
    assert sorted(guest["done"]) == sorted(units[:2])

    # Signing in offers to bring them over, and "Bring over" does.
    sign_in(page, site, learner.email, units[2])
    banner = page.locator(".learn-banner")
    assert "2 pages marked done" in banner.inner_text()
    with page.expect_navigation():
        banner.get_by_role("button", name="Bring over").click()
    assert statuses(learner) == {units[0]: "studied", units[1]: "studied"}
    assert page.locator(".learn-banner").count() == 0
    assert sorted(stored(page)["done"]) == sorted(units[:2])

    # Marking a unit while signed in reaches the account.
    assert page.locator(TOGGLE).first.inner_text() == "Mark this unit done"
    mark(page)
    assert statuses(learner)[units[2]] == "studied"
    page.goto(f"{site}/me/")
    assert f"3 of {len(units)} units done" in page.content()

    # A second device sees the same progress, and is not offered the import again.
    other = browser.new_context()
    second = other.new_page()
    sign_in(second, site, learner.email, units[0])
    assert second.locator(TOGGLE).first.inner_text() == "Done ✓ (undo)"
    assert second.locator(".learn-banner").count() == 0
    second.goto(f"{site}/{COURSE}/index.html")
    assert f"3 of {len(units)} done" in second.locator("p.progress-line").inner_text()
    # Undoing it there is saved too.
    second.goto(f"{site}/{units[0]}")
    mark(second)
    assert statuses(learner)[units[0]] == "not_started"
    other.close()

    # Signing out gives this browser the guest's own progress back.
    page.goto(f"{site}/me/")
    with page.expect_navigation():
        page.get_by_role("button", name="Sign out").click()
    page.goto(f"{site}/{units[2]}")
    assert stored(page)["done"] == guest["done"]
    assert page.locator(TOGGLE).first.inner_text() == "Mark this unit done"
    leftovers = page.evaluate("() => ['nrstatlab.account', 'nrstatlab.progress.v1.guest'].map(k => localStorage.getItem(k))")
    assert leftovers == [None, None]


def test_not_now_closes_the_offer_for_good(page, site, units, learner):
    page.goto(f"{site}/{units[0]}")
    mark(page, expect_saved=False)
    sign_in(page, site, learner.email, units[1])
    with page.expect_navigation():
        page.locator(".learn-banner").get_by_role("button", name="Not now").click()
    assert page.locator(".learn-banner").count() == 0
    assert not UnitProgress.objects.exists()
    page.goto(f"{site}/{units[2]}")
    assert page.locator(".learn-banner").count() == 0


def test_a_failed_save_says_so(page, site, units, learner):
    sign_in(page, site, learner.email, units[0])
    page.route("**/me/progress/studied", lambda route: route.abort())
    mark(page, expect_saved=False)
    note = page.locator(".progress-toggle .learn-note").first
    note.wait_for()
    assert "Not saved" in note.inner_text()
    assert not UnitProgress.objects.exists()


def test_a_passed_unit_stays_done(page, site, units, learner):
    UnitProgress.objects.create(user=learner, unit=Unit.objects.get(legacy_path=units[0]), status="passed")
    sign_in(page, site, learner.email, units[0])
    assert page.locator(TOGGLE).first.inner_text() == "Done ✓ (undo)"
    mark(page)
    page.locator(".progress-toggle .learn-note").first.wait_for()
    assert page.locator(TOGGLE).first.inner_text() == "Done ✓ (undo)"
    assert units[0] in stored(page)["done"]
    assert statuses(learner) == {units[0]: "passed"}


def test_the_account_state_block_is_valid_json_on_every_kind_of_page(page, site, learner):
    sign_in(page, site, learner.email, "index.html")
    for path in ["index.html", f"{COURSE}/index.html", "about.html", "me/", "privacy.html"]:
        page.goto(f"{site}/{path}")
        state = json.loads(page.locator("#nrstat-account").text_content())
        assert state["signed_in"] is True, path
