"""Item analysis and the reviewer workflow (BUILD-GUIDE Step 13).

The done-when fixture, worked by hand: 40 sittings of ten other questions each; the
question under study is right in 20 of them, whose rest-scores (the share of the other
ten right) are all 0.8, and wrong in 20, ten at 0.2 and ten at 0.6.
    p = 20/40 = 0.500; M1 = 0.8; M0 = 0.4; mean R = (16 + 2 + 6)/40 = 0.6
    s^2 = (20 x 0.2^2 + 10 x 0.4^2 + 10 x 0^2)/40 = 0.06; s = 0.244949
    r_pb = (0.8 - 0.4)/0.244949 x sqrt(0.5 x 0.5) = 0.816
Swapping who got it right gives r_pb = -0.816, and the question is flagged."""
import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.assessments import engine, review, stats
from apps.assessments.models import Attempt, ItemStats, Question, QuestionEvent, Response, UnitTest

pytestmark = pytest.mark.django_db
UNIT = "exams/ugc-net/unit1.html"
# No question imports as flagged since the owner settled the review queue on 2 October 2026,
# so these three are put in review for each test, as a reviewer or the statistics would.
IN_REVIEW = ["appsc-aso-2022-q140", "ugc-mcq-u02-q45", "ugc-mcq-u05-q41"]


@pytest.fixture(autouse=True)
def in_review():
    Question.objects.filter(uid__in=IN_REVIEW).update(status=Question.FLAGGED, flag_reason="Put in review for a test.")


@pytest.fixture
def items():
    ut = UnitTest.objects.get(unit__legacy_path=UNIT)
    pool = engine.pool(ut)
    return ut, pool[0], pool[1:11]


def sit(ut, x, others, x_right, k, i=0, kind=Attempt.UNIT_TEST, mode="", submitted=True, x_counts=True):
    """One sitting: x answered right or wrong, and k of the ten others right (which ones
    turns with i, so each other question has a spread of answers)."""
    uids = [x.uid] + [o.uid for o in others]
    a = Attempt.objects.create(user=None, kind=kind, unit_test=ut if kind == Attempt.UNIT_TEST else None, mode=mode,
                               seed=i, question_uids=uids, submitted_at=timezone.now() if submitted else None)
    rows = [Response(attempt=a, question=x, answer="x", correct=x_right if x_counts else None)]
    rows += [Response(attempt=a, question=o, answer="x", correct=(i + j) % 10 < k) for j, o in enumerate(others)]
    Response.objects.bulk_create(rows)
    return a


def fixture(ut, x, others, negative=False, n=40, **kw):
    """The hand-worked 40 sittings (see the module's docstring)."""
    groups = [(True, 8)] * 20 + [(False, 2)] * 10 + [(False, 6)] * 10
    if negative:
        groups = [(False, 8)] * 20 + [(True, 2)] * 10 + [(True, 6)] * 10
    for i, (right, k) in enumerate(groups[:n]):
        sit(ut, x, others, right, k, i, **kw)


@pytest.fixture
def reviewer(make_learner):
    u = make_learner("reviewer@example.com", "Kavya")
    u.is_staff = True
    u.save()
    u.groups.add(Group.objects.get(name=review.REVIEWERS))
    return u


# ---------------------------------------------------------------- the done-when tests

def test_the_fixture_gives_p_and_r_pb_to_three_decimals(items):
    ut, x, others = items
    fixture(ut, x, others)
    stats.run(notify=False)
    s = ItemStats.objects.get(question=x)
    assert (s.n, round(s.difficulty, 3), round(s.point_biserial, 3)) == (40, 0.5, 0.816)
    assert Question.objects.get(pk=x.pk).status == Question.PUBLISHED


def test_a_negative_r_pb_is_flagged_automatically_and_the_reviewers_are_told(items, reviewer):
    ut, x, others = items
    fixture(ut, x, others, negative=True)
    summary = stats.run()
    x.refresh_from_db()
    assert round(x.stats.point_biserial, 3) == -0.816
    assert x.status == Question.FLAGGED and "r_pb is negative (-0.816)" in x.flag_reason
    assert x.uid in [uid for uid, _ in summary["flagged"]]
    assert x.events.filter(action=QuestionEvent.STATS_FLAGGED, to_status=Question.FLAGGED).count() == 1
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [reviewer.email] and x.uid in mail.outbox[0].body


def test_the_formula_on_its_own():
    pairs = [(True, 0.8)] * 20 + [(False, 0.2)] * 10 + [(False, 0.6)] * 10
    f = stats.figures(pairs)
    assert (f.n, round(f.p, 3), round(f.r_pb, 3)) == (40, 0.5, 0.816)
    assert stats.figures([(True, 0.5)] * 30).r_pb is None            # no one wrong: not defined
    assert stats.figures([(True, 0.5)] * 15 + [(False, 0.5)] * 15).r_pb is None   # s = 0


def test_the_three_reasons_to_flag():
    assert stats.reasons(stats.Figures(40, 0.5, -0.01)) and not stats.reasons(stats.Figures(40, 0.5, 0.0))
    assert stats.reasons(stats.Figures(40, 0.951, 0.2)) and not stats.reasons(stats.Figures(40, 0.95, 0.2))
    assert stats.reasons(stats.Figures(40, 0.099, 0.2)) and not stats.reasons(stats.Figures(40, 0.10, 0.2))


# ---------------------------------------------------------------- what counts

def test_fewer_than_thirty_responses_are_not_analysed(items):
    ut, x, others = items
    fixture(ut, x, others, negative=True, n=29)
    stats.run(notify=False)
    assert not ItemStats.objects.filter(question=x).exists()
    assert Question.objects.get(pk=x.pk).status == Question.PUBLISHED


def test_practice_and_unsubmitted_sittings_do_not_count_but_exams_do(items):
    ut, x, others = items
    fixture(ut, x, others, negative=True, kind=Attempt.PAPER, mode="practice")
    fixture(ut, x, others, negative=True, submitted=False)
    stats.run(notify=False)
    assert not ItemStats.objects.filter(question=x).exists()
    fixture(ut, x, others, negative=True, kind=Attempt.PAPER, mode="exam")
    stats.run(notify=False)
    assert ItemStats.objects.get(question=x).n == 40


def test_a_response_that_did_not_count_is_left_out(items):
    ut, x, others = items
    fixture(ut, x, others, x_counts=False)
    stats.run(notify=False)
    assert not ItemStats.objects.filter(question=x).exists()
    assert ItemStats.objects.get(question=others[0]).n == 40         # the others still count


def test_only_published_questions_are_flagged(items):
    ut, x, others = items
    Question.objects.filter(pk=x.pk).update(status=Question.DRAFT)
    fixture(ut, x, others, negative=True)
    stats.run(notify=False)
    assert Question.objects.get(pk=x.pk).status == Question.DRAFT
    assert ItemStats.objects.get(question=x).point_biserial < 0


def test_an_approved_question_is_flagged_again_only_on_thirty_more_responses(items, reviewer):
    ut, x, others = items
    fixture(ut, x, others, negative=True)
    stats.run(notify=False)
    review.approve(x, reviewer)
    assert ItemStats.objects.get(question=x).cleared_at_n == 40
    fixture(ut, x, others, negative=True, n=29)                       # 69: not yet 30 more
    stats.run(notify=False)
    assert Question.objects.get(pk=x.pk).status == Question.PUBLISHED
    fixture(ut, x, others, negative=True, n=1)                        # 70
    stats.run(notify=False)
    assert Question.objects.get(pk=x.pk).status == Question.FLAGGED


def test_the_command(items, capsys):
    from django.core.management import call_command

    ut, x, others = items
    fixture(ut, x, others, negative=True)
    call_command("item_stats", "--no-email")
    out = capsys.readouterr().out
    assert "flagged for review" in out and x.uid in out and not mail.outbox


# ---------------------------------------------------------------- the reviewer workflow

def test_approve_publishes_and_records_the_reviewer(reviewer):
    q = Question.objects.filter(status=Question.FLAGGED).first()
    reason = q.flag_reason
    review.approve(q, reviewer, "Key checked by hand.")
    q.refresh_from_db()
    assert (q.status, q.reviewer, q.flag_reason) == (Question.PUBLISHED, reviewer, "")
    assert q.reviewed_at is not None
    e = q.events.get(action=QuestionEvent.APPROVED)
    assert (e.user, e.from_status, e.to_status, e.note) == (reviewer, "flagged", "published", "Key checked by hand.")
    assert e.changes == {"flag_reason": [reason, ""]}


def test_no_one_approves_their_own_question(reviewer, make_learner):
    q = Question.objects.filter(status=Question.FLAGGED).first()
    Question.objects.filter(pk=q.pk).update(author=reviewer)
    with pytest.raises(review.ReviewRefused, match="another reviewer"):
        review.approve(q, reviewer)
    assert Question.objects.get(pk=q.pk).status == Question.FLAGGED
    stranger = make_learner("staff@example.com")
    stranger.is_staff = True
    stranger.save()
    with pytest.raises(review.ReviewRefused, match="Only a reviewer"):
        review.approve(q, stranger)


def test_a_question_without_a_key_cannot_be_published(reviewer):
    none_right = Question.objects.get(uid="appsc-aso-2025-q134")          # no option is correct: retired
    with pytest.raises(review.ReviewRefused, match="retired"):
        review.approve(none_right, reviewer)
    Question.objects.filter(pk=none_right.pk).update(status=Question.FLAGGED)
    with pytest.raises(review.ReviewRefused, match="no key"):
        review.approve(none_right, reviewer)
    assert Question.objects.get(pk=none_right.pk).status == Question.FLAGGED


def test_send_back_needs_a_note(reviewer):
    q = Question.objects.filter(status=Question.FLAGGED).first()
    with pytest.raises(review.ReviewRefused, match="note is required"):
        review.send_back(q, reviewer, "  ")
    review.send_back(q, reviewer, "Option C is misprinted.")
    q.refresh_from_db()
    assert q.status == Question.DRAFT and q.flag_reason == "Sent back: Option C is misprinted."
    assert q.events.get(action=QuestionEvent.SENT_BACK).note == "Option C is misprinted."


def test_every_question_has_a_history_from_its_import():
    assert not Question.objects.filter(events__isnull=True).exists()
    for uid, status in [("ugc-mcq-u07-q14", Question.PUBLISHED), ("appsc-aso-2025-q134", Question.RETIRED)]:
        first = Question.objects.get(uid=uid).events.first()
        assert (first.action, first.to_status) == (QuestionEvent.IMPORTED, status), uid


def test_a_change_in_the_source_is_recorded(source):
    from apps.assessments import bank
    from apps.core.questions import read_bank

    b = read_bank(source.root)
    items = [dict(i) for i in b.sources["ugc-mcq-"]]
    items[0]["solution_html"] = items[0]["solution_html"] + "<p>More.</p>"
    bank.store_questions(items, prefix="ugc-mcq-")
    q = Question.objects.get(uid=items[0]["uid"])
    assert q.events.last().action == QuestionEvent.SOURCE_CHANGED


# ---------------------------------------------------------------- the admin

@pytest.fixture
def staff_client(reviewer):
    c = Client()
    c.force_login(reviewer)
    return c


def test_the_queue_lists_draft_and_flagged_questions_only(staff_client):
    html = staff_client.get("/staff/assessments/reviewquestion/").content.decode()
    flagged = Question.objects.filter(status__in=[Question.FLAGGED, Question.DRAFT]).count()
    assert f"{flagged} questions in the review queue" in html
    published = Question.objects.filter(status=Question.PUBLISHED).first()
    assert published.uid not in html


def test_the_queue_is_for_reviewers_only(make_learner):
    staff = make_learner("staff@example.com")
    staff.is_staff = True
    staff.save()
    c = Client()
    c.force_login(staff)
    assert c.get("/staff/assessments/reviewquestion/").status_code == 403
    q = Question.objects.filter(status=Question.FLAGGED).first()
    assert c.get(f"/staff/assessments/reviewquestion/{q.pk}/change/").status_code == 403


def test_the_review_page_side_by_side(staff_client):
    q = Question.objects.filter(status=Question.FLAGGED, uid__startswith="ugc-mcq-").first()
    html = staff_client.get(f"/staff/assessments/reviewquestion/{q.pk}/change/").content.decode()
    key = q.choices.get(is_correct=True).label
    assert "As the learner sees it" in html and "The key and the working" in html
    assert f"Key: {key}" in html and "Recompute log" in html and "mathjax" in html.lower()
    assert "History" in html and "imported" in html


def test_approve_and_send_back_from_the_page(staff_client, reviewer):
    q1, q2 = Question.objects.filter(status=Question.FLAGGED)[:2]
    r = staff_client.post(f"/staff/assessments/reviewquestion/{q1.pk}/change/", {"action": "approve", "note": ""})
    assert r.status_code == 302 and Question.objects.get(pk=q1.pk).status == Question.PUBLISHED
    r = staff_client.post(f"/staff/assessments/reviewquestion/{q2.pk}/change/", {"action": "send_back", "note": ""})
    assert Question.objects.get(pk=q2.pk).status == Question.FLAGGED          # refused: no note
    staff_client.post(f"/staff/assessments/reviewquestion/{q2.pk}/change/", {"action": "send_back", "note": "Recheck."})
    assert Question.objects.get(pk=q2.pk).status == Question.DRAFT


def test_the_author_cannot_approve_from_the_page(staff_client, reviewer):
    q = Question.objects.filter(status=Question.FLAGGED).first()
    Question.objects.filter(pk=q.pk).update(author=reviewer)
    html = staff_client.get(f"/staff/assessments/reviewquestion/{q.pk}/change/").content.decode()
    assert "You wrote this question" in html
    staff_client.post(f"/staff/assessments/reviewquestion/{q.pk}/change/", {"action": "approve"})
    assert Question.objects.get(pk=q.pk).status == Question.FLAGGED


def test_publishing_by_editing_the_status_is_refused(django_user_model):
    from apps.assessments.admin import QuestionForm

    q = Question.objects.filter(status=Question.FLAGGED).first()
    form = QuestionForm(instance=q)
    data = {k: v for k, v in form.initial.items() if v is not None}
    data["status"] = Question.PUBLISHED
    bound = QuestionForm(data=data, instance=q)
    assert not bound.is_valid() and "review queue" in str(bound.errors["status"])


def test_an_edit_in_the_admin_is_recorded(django_user_model):
    admin_user = django_user_model.objects.create_superuser("admin@example.com", "a-long-password-1")
    c = Client()
    c.force_login(admin_user)
    q = Question.objects.filter(status=Question.FLAGGED).first()
    page = c.get(f"/staff/assessments/question/{q.pk}/change/")
    form = page.context["adminform"].form
    data = {k: ("" if v is None else v) for k, v in form.initial.items() if k not in ("author", "reviewer")}
    data.update({"status": Question.RETIRED, "tags": "[]"})
    for fs in page.context["inline_admin_formsets"]:
        mgmt = fs.formset.management_form
        for name in ("TOTAL_FORMS", "INITIAL_FORMS", "MIN_NUM_FORMS", "MAX_NUM_FORMS"):
            data[f"{mgmt.prefix}-{name}"] = mgmt.initial.get(name, 0) if name != "TOTAL_FORMS" else 0
        data[f"{mgmt.prefix}-INITIAL_FORMS"] = 0
    r = c.post(f"/staff/assessments/question/{q.pk}/change/", data)
    assert r.status_code == 302, r.context["adminform"].form.errors if r.context else r
    e = q.events.last()
    assert (e.action, e.user, e.from_status, e.to_status) == (QuestionEvent.EDITED, admin_user, "flagged", "retired")
