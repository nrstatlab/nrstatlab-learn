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
        call_command("import_questions", verbosity=0)
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


UGC7 = "exams/ugc-net/unit7.html"


def test_a_guest_is_told_about_the_test_even_with_storage_blocked(browser, site):
    ctx = browser.new_context()
    ctx.add_init_script("Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});")
    page = ctx.new_page()
    page.goto(f"{site}/{UGC7}")
    box = page.locator(".learn-test")
    assert "10 questions, pass at 70%" in box.inner_text() and "Sign in" in box.inner_text()
    assert page.locator(TOGGLE).count() == 0
    ctx.close()


def test_a_learner_takes_a_unit_test_from_the_unit_page(page, site, learner):
    from apps.assessments.models import Attempt

    from .test_unit_tests import correct_answers

    sign_in(page, site, learner.email, UGC7)
    box = page.locator(".learn-test")
    assert "It opens when you mark this unit done" in box.inner_text()
    mark(page)
    box.get_by_role("link", name="Take the test").click()
    page.get_by_role("button", name="Start the test").click()
    page.wait_for_url(f"{site}/test/attempt/**")
    attempt = Attempt.objects.get(user=learner)
    assert page.locator("fieldset.tq").count() == 10
    for n, token in correct_answers(attempt).items():
        with page.expect_response(lambda r: r.url.endswith("/answer")) as resp:
            page.locator(f'fieldset.tq[data-n="{n}"] input[value="{token}"]').check()
        assert resp.value.ok
    assert attempt.responses.count() == 10
    page.get_by_role("button", name="Submit the test").click()
    page.wait_for_url(f"{site}/test/attempt/{attempt.pk}/result")
    assert "10 of 10" in page.locator(".tr-summary").inner_text()
    page.goto(f"{site}/{UGC7}")
    assert "Passed, best 100%" in page.locator(".learn-test").inner_text()
    assert page.locator(TOGGLE).first.inner_text() == "Done ✓ (undo)"


def test_unanswered_questions_are_confirmed_before_submitting(page, site, learner):
    from apps.progress import services as progress
    progress.mark_studied(learner, UGC7)
    sign_in(page, site, learner.email, UGC7)
    page.locator(".learn-test a").click()
    page.get_by_role("button", name="Start the test").click()
    page.wait_for_url(f"{site}/test/attempt/**")
    messages = []
    page.on("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    page.get_by_role("button", name="Submit the test").click()
    assert messages == ["10 questions are not answered. Submit anyway?"]
    assert "/result" not in page.url


def sign_in_to(page, site, email, path):
    """Sign in on the sign-in page itself, then land on path (which may need a signed-in learner)."""
    page.goto(f"{site}/accounts/login/?next=/{path}")
    page.fill("input[name=login]", email)
    page.fill("input[name=password]", PASSWORD)
    page.locator("form button[type=submit]").click()
    page.wait_for_url(f"{site}/{path}")


def _paper_tok(sitting, n, correct=True):
    from apps.assessments import engine
    from apps.assessments.models import Question
    uid = sitting.attempt.question_uids[n - 1]
    choice = Question.objects.get(uid=uid).choices.filter(is_correct=correct).first()
    return engine.token(sitting.attempt, uid, "option", choice.label)


def test_sit_the_appsc_2025_paper_from_its_solved_page(page, site, learner):
    from apps.papers.models import PaperAttempt

    sign_in(page, site, learner.email, "exams/appsc/solved-2025-paper-ii.html")
    box = page.locator(".learn-paper")
    assert "150 minutes" in box.inner_text() and "0.33 for a wrong answer" in box.inner_text()
    box.get_by_role("link").click()
    page.get_by_role("button", name="Sit the paper").click()
    page.wait_for_url(f"{site}/papers/attempt/**")
    clock = page.locator("#exam-clock")
    first = clock.inner_text()
    page.wait_for_timeout(1500)
    assert first != clock.inner_text() and "left" in clock.inner_text()
    q134 = page.locator("#q134")
    assert q134.locator("input").count() == 0 and "Withdrawn by the Commission" in q134.inner_text()
    s = PaperAttempt.objects.get(attempt__user=learner)
    for n in (1, 2, 3, 4, 5):                       # all five are counted questions, answered right
        with page.expect_response(lambda r: r.url.endswith("/answer")):
            page.locator(f'fieldset[data-n="{n}"] input[value="{_paper_tok(s, n)}"]').check()
    assert page.locator("#exam-answered").inner_text() == "5"
    assert page.locator('.exam-grid a.is-answered').count() == 5
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Submit the paper").click()
    page.wait_for_url(f"{site}/papers/attempt/{s.attempt_id}/review")
    assert "5.00 of 140.00" in page.locator(".tr-summary").inner_text()
    assert "not counted" in page.locator("#q134").inner_text()


def test_practise_the_ugc_2026_paper_and_come_back_to_the_same_place(page, site, learner):
    from apps.papers.models import PaperAttempt

    sign_in_to(page, site, learner.email, "papers/ugc-net-june-2026/")
    assert "No timer" in page.content()
    page.get_by_role("button", name="Practise").click()
    page.wait_for_url(f"{site}/papers/attempt/**")
    s = PaperAttempt.objects.get(attempt__user=learner)
    page.locator(f'input[value="{_paper_tok(s, 1, correct=False)}"]').check()
    page.get_by_role("button", name="Check my answer").click()
    assert "Not quite." in page.locator(".practice-verdict").inner_text()
    assert page.locator(".tq-options li.is-key").count() == 1
    page.get_by_role("link", name="Next →").click()
    page.get_by_role("button", name="Show the solution").click()
    assert "The answer:" in page.locator(".practice-verdict").inner_text()
    page.goto(f"{site}/papers/ugc-net-june-2026/")
    page.get_by_role("button", name="Carry on practising").click()
    assert page.locator("h1").inner_text().startswith("Q2")


def test_the_clock_submits_the_paper_when_it_runs_out(page, site, learner):
    from datetime import timedelta

    from django.utils import timezone

    from apps.papers.models import PaperAttempt

    sign_in_to(page, site, learner.email, "papers/appsc-aso-2022-paper-ii/")
    page.get_by_role("button", name="Sit the paper").click()
    page.wait_for_url(f"{site}/papers/attempt/**")
    s = PaperAttempt.objects.get(attempt__user=learner)
    PaperAttempt.objects.filter(pk=s.pk).update(deadline=timezone.now() + timedelta(seconds=3))
    page.reload()
    page.wait_for_url(f"{site}/papers/attempt/{s.attempt_id}/review", timeout=15000)
    s.attempt.refresh_from_db()
    assert s.attempt.submitted_at is not None


def test_readiness_from_an_exams_map_rises_with_a_passed_test(page, site, learner):
    """CSIR NET: UGC NET Unit II is the only unit link of 10 of its 39 counted lines, so
    passing its test takes readiness from 0% to 10/39 = 25.6%."""
    from apps.assessments import services as assessments
    from apps.progress import services as progress

    sign_in_to(page, site, learner.email, "exams/csir-net/index.html")
    box = page.locator(".learn-ready")
    assert "Your readiness for CSIR NET Mathematical Sciences: 0%" in box.inner_text()
    box.get_by_role("link", name="See what to study next").click()
    page.wait_for_url(f"{site}/readiness/csir-net/")
    assert page.locator(".ready-figure").inner_text() == "0% ready"
    progress.mark_studied(learner, "exams/ugc-net/unit2.html")
    assessments.sit_test(learner, "exams/ugc-net/unit2.html", right=10)
    page.reload()
    assert page.locator(".ready-figure").inner_text() == "25.6% ready"
    page.get_by_role("button", name="Make this my exam").click()
    page.wait_for_url(f"{site}/readiness/csir-net/")
    assert "This is your exam." in page.content()
    page.goto(f"{site}/me/")
    card = page.locator(".ready-card")
    assert "CSIR NET Mathematical Sciences: 25.6% ready" in card.inner_text()
