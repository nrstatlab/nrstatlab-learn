"""The unit test engine and its pages (BUILD-GUIDE Step 10): unlocking, drawing and
retakes, every question type, scoring on the server, and no answer in the page
before submission."""
import json
import re
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.test import Client

from apps.assessments import engine
from apps.assessments.models import Attempt, Choice, Question, QuestionUnit, UnitTest
from apps.progress import services as progress
from apps.progress.models import UnitProgress
from apps.study.models import Course, Unit

pytestmark = pytest.mark.django_db
UGC7 = "exams/ugc-net/unit7.html"


def ut_for(path):
    return UnitTest.objects.get(unit__legacy_path=path)


def correct_answers(attempt):
    """What a learner who knows every answer would send: tokens, as the page shows them."""
    out = {}
    for n, uid in enumerate(attempt.question_uids, 1):
        q = Question.objects.get(uid=uid)
        if q.qtype == Question.MATCH:
            out[n] = {k: engine.token(attempt, uid, "right", v) for k, v in json.loads(q.answer_text).items()}
        elif q.qtype == Question.NUMERIC:
            out[n] = q.answer_text
        elif q.qtype == Question.MULTIPLE:
            out[n] = [engine.token(attempt, uid, "option", c.label) for c in q.choices.filter(is_correct=True)]
        else:
            out[n] = engine.token(attempt, uid, "option", q.choices.get(is_correct=True).label)
    return out


def wrong_token(attempt, n):
    uid = attempt.question_uids[n - 1]
    return engine.token(attempt, uid, "option", Question.objects.get(uid=uid).choices.filter(is_correct=False).first().label)


@pytest.fixture
def mixed_unit():
    """A unit with two questions of each type (ten in all), for the scoring tests."""
    course = Course.objects.get(path="statistics/sampling-theory")
    unit = Unit.objects.create(legacy_path="statistics/sampling-theory/fixture.html", title="Fixture unit",
                               body_html="x", content_hash="x", course=course, order=99)
    ut = UnitTest.objects.create(unit=unit)

    def make(uid, qtype, choices=(), answer_text="", tolerance=None):
        q = Question.objects.create(uid=uid, qtype=qtype, stem_html=f"<p>Stem {uid.replace('t-', 'q ')}</p>",
                                    solution_html=f"Working {uid}",
                                    answer_text=answer_text, tolerance=tolerance, source="test", status="published")
        for i, c in enumerate(choices):
            Choice.objects.create(question=q, label=c[0], text_html=c[1], is_correct=c[2],
                                  side=c[3] if len(c) > 3 else "", order=i)
        QuestionUnit.objects.create(question=q, unit=unit)
        return q
    abcd = lambda key: [(k, f"option {k}", k == key) for k in "ABCD"]  # noqa: E731
    for i in (1, 2):
        make(f"t-single-{i}", "single", abcd("C"))
        make(f"t-assert-{i}", "assertion", abcd("A"))
        make(f"t-multi-{i}", "multiple", [("A", "a", True), ("B", "b", False), ("C", "c", True), ("D", "d", False)])
        make(f"t-num-{i}", "numeric", answer_text="0.58", tolerance=Decimal("0.005"))
        make(f"t-match-{i}", "match", [("A", "alpha", False, "left"), ("B", "beta", False, "left"),
                                       ("I", "one", False, "right"), ("II", "two", False, "right")],
             answer_text=json.dumps({"A": "II", "B": "I"}))
    return ut


# ---------------------------------------------------------------- unlocking

def test_a_test_opens_only_after_the_unit_is_studied(learner):
    ut = ut_for(UGC7)
    with pytest.raises(engine.TestLocked):
        engine.start(learner, ut)
    progress.mark_studied(learner, UGC7)
    assert engine.start(learner, ut).question_uids


def test_a_unit_needs_enough_published_questions(learner):
    thin = UnitTest.objects.get(unit__legacy_path="statistics/sampling-techniques/unit1.html")  # 3 questions
    progress.mark_studied(learner, thin.unit.legacy_path)
    assert engine.test_for_unit(thin.unit) is None
    with pytest.raises(engine.TestLocked):
        engine.start(learner, thin)


def test_thirty_unit_tests_are_open_today():
    """Nineteen until 2 October 2026, when the settled answers gave Applied Statistics Unit 3 its tenth;
    thirty from 3 October, when the owner approved the ten units of UGC NET Paper I."""
    open_ = [ut.unit.legacy_path for ut in UnitTest.objects.select_related("unit") if engine.test_for_unit(ut.unit)]
    assert len(open_) == 30 and all(f"exams/ugc-net/unit{i}.html" in open_ for i in range(1, 11))
    assert all(f"exams/ugc-net/paper-1/unit{i}.html" in open_ for i in range(1, 11))
    assert "statistics/applied-statistics/unit3.html" in open_


def test_one_open_attempt_per_learner_per_test(learner):
    progress.mark_studied(learner, UGC7)
    ut = ut_for(UGC7)
    a = engine.start(learner, ut)
    assert engine.start(learner, ut).pk == a.pk
    with pytest.raises(IntegrityError), transaction.atomic():
        Attempt.objects.create(user=learner, kind="unit_test", unit_test=ut, seed=1, question_uids=[])


# ---------------------------------------------------------------- drawing

def test_the_draw_takes_published_questions_of_the_unit_only(learner):
    ut = ut_for("exams/ugc-net/unit5.html")
    Question.objects.filter(uid__in=["ugc-mcq-u05-q50", "ugc-mcq-u05-q41"]).update(status="flagged")  # two in review
    for seed in range(40):
        uids = engine.draw(ut, learner, seed)
        assert len(uids) == len(set(uids)) == 10
        qs = Question.objects.filter(uid__in=uids)
        assert all(q.status == "published" for q in qs)
        assert all(q.unit_links.filter(unit=ut.unit).exists() for q in qs)
        assert "ugc-mcq-u05-q50" not in uids and "ugc-mcq-u05-q41" not in uids


def test_the_same_seed_draws_the_same_test(learner):
    ut = ut_for(UGC7)
    assert engine.draw(ut, learner, 7) == engine.draw(ut, learner, 7) != engine.draw(ut, learner, 8)


def test_a_retake_draws_unseen_questions_first(learner):
    progress.mark_studied(learner, UGC7)
    ut = ut_for(UGC7)
    Question.objects.filter(uid="ugc-mcq-u07-q14").update(status="flagged")   # one in review: 49 published
    seen = set()
    for _ in range(4):                       # 49 published: four tests of ten are all new
        a = engine.start(learner, ut)
        assert not seen & set(a.question_uids)
        seen |= set(a.question_uids)
        engine.submit(a)
    a = engine.start(learner, ut)            # only nine unseen remain: all nine, then one seen
    assert len(set(a.question_uids) - seen) == 9


def test_the_draw_balances_difficulty(learner):
    ut = ut_for(UGC7)
    uids = [q.uid for q in engine.pool(ut)]
    for i, uid in enumerate(uids):
        Question.objects.filter(uid=uid).update(difficulty=(1, 3, 5)[i % 3])
    for seed in range(20):
        bands = [engine.band(q) for q in Question.objects.filter(uid__in=engine.draw(ut, learner, seed))]
        counts = sorted(bands.count(b) for b in ("easy", "medium", "hard"))
        assert counts[-1] - counts[0] <= 1, counts


# ---------------------------------------------------------------- scoring, every type

def start_mixed(learner, ut):
    progress.mark_studied(learner, ut.unit.legacy_path)
    return engine.start(learner, ut)


def test_every_question_type_scores_right_when_right(learner, mixed_unit):
    a = start_mixed(learner, mixed_unit)
    for n, raw in correct_answers(a).items():
        engine.save_answer(a, n, raw)
    a = engine.submit(a)
    assert (a.score, a.max_score) == (10, 10)
    assert UnitProgress.objects.get(user=learner, unit=mixed_unit.unit).status == "passed"


@pytest.mark.parametrize("qtype,make_wrong", [
    ("single", lambda a, n, q, right: wrong_token(a, n)),
    ("assertion", lambda a, n, q, right: wrong_token(a, n)),
    ("multiple", lambda a, n, q, right: right[:1]),                                   # a subset is not enough
    ("multiple", lambda a, n, q, right: right + [wrong_token(a, n)]),                  # nor is a superset
    ("numeric", lambda a, n, q, right: "0.586"),                                       # just outside 0.005
    ("match", lambda a, n, q, right: dict(right, B=right["A"])),                       # one pair wrong
])
def test_every_question_type_scores_wrong_when_wrong(learner, mixed_unit, qtype, make_wrong):
    a = start_mixed(learner, mixed_unit)
    answers = correct_answers(a)
    targets = [n for n, uid in enumerate(a.question_uids, 1) if Question.objects.get(uid=uid).qtype == qtype]
    for n, raw in answers.items():
        q = Question.objects.get(uid=a.question_uids[n - 1])
        engine.save_answer(a, n, make_wrong(a, n, q, raw) if n in targets else raw)
    a = engine.submit(a)
    assert (a.score, a.max_score) == (10 - len(targets), 10)


def test_a_numeric_answer_on_the_tolerance_is_right(learner, mixed_unit):
    a = start_mixed(learner, mixed_unit)
    for n, raw in correct_answers(a).items():
        qtype = Question.objects.get(uid=a.question_uids[n - 1]).qtype
        engine.save_answer(a, n, "0.585" if qtype == "numeric" else raw)
    assert engine.submit(a).score == 10
    with pytest.raises(engine.BadAnswer):
        engine.normalise(a, Question.objects.get(uid="t-num-1"), "about half")


def test_a_question_flagged_after_the_draw_is_not_scored(learner):
    progress.mark_studied(learner, UGC7)
    a = engine.start(learner, ut_for(UGC7))
    for n, raw in correct_answers(a).items():
        engine.save_answer(a, n, raw)
    Question.objects.filter(uid=a.question_uids[0]).update(status="flagged", flag_reason="Key in doubt")
    a = engine.submit(a)
    assert (a.score, a.max_score) == (9, 9)
    assert engine.result_view(a)["voided"] == 1


def test_a_flagged_question_can_never_be_scored(learner):
    """Even forced into an attempt, a flagged question counts neither for nor against."""
    Question.objects.filter(uid__in=["ugc-mcq-u05-q50", "ugc-mcq-u05-q41"]).update(status="flagged")
    progress.mark_studied(learner, "exams/ugc-net/unit5.html")
    a = engine.start(learner, ut_for("exams/ugc-net/unit5.html"))
    a.question_uids = ["ugc-mcq-u05-q50", "ugc-mcq-u05-q41"] + a.question_uids[2:]
    a.save()
    for n, raw in correct_answers(a).items():
        engine.save_answer(a, n, raw)
    a = engine.submit(a)
    assert (a.score, a.max_score) == (8, 8)


def test_a_pass_marks_the_unit_passed_and_a_fail_does_not(learner):
    progress.mark_studied(learner, UGC7)
    ut = ut_for(UGC7)
    a = engine.start(learner, ut)
    answers = correct_answers(a)
    for n in range(1, 11):
        engine.save_answer(a, n, answers[n] if n <= 6 else wrong_token(a, n))   # 60%
    engine.submit(a)
    row = UnitProgress.objects.get(user=learner, unit=ut.unit)
    assert (row.status, row.best_score) == ("studied", Decimal("60.00"))
    a = engine.start(learner, ut)
    answers = correct_answers(a)
    for n in range(1, 11):
        engine.save_answer(a, n, answers[n] if n <= 7 else wrong_token(a, n))   # 70%: the pass mark
    engine.submit(a)
    row.refresh_from_db()
    assert (row.status, row.best_score) == ("passed", Decimal("70.00"))
    a = engine.start(learner, ut)
    engine.submit(a)                                                          # 0%: the best is kept
    row.refresh_from_db()
    assert (row.status, row.best_score) == ("passed", Decimal("70.00"))
    assert progress.mark_studied(learner, UGC7, False) == "passed"
    assert [t["score"] for t in progress.recent_tests(learner)] == ["0.00", "70.00", "60.00"]


def test_a_submitted_attempt_cannot_change(learner):
    progress.mark_studied(learner, UGC7)
    a = engine.submit(engine.start(learner, ut_for(UGC7)))
    with pytest.raises(engine.AttemptClosed):
        engine.save_answer(a, 1, correct_answers(a)[1])
    assert engine.submit(a).score == 0


# ---------------------------------------------------------------- the pages

def body(r):
    return r.content.decode()


def test_the_test_page_gives_no_answer_away(client, learner, mixed_unit):
    client.force_login(learner)
    a = start_mixed(learner, mixed_unit)
    html = body(client.get(f"/test/attempt/{a.pk}/"))
    assert html.count('class="tq"') == 10
    for uid in a.question_uids:
        q = Question.objects.get(uid=uid)
        assert q.solution_html not in html
        if q.answer_text:
            assert q.answer_text not in html
    for word in ("is_correct", "is-key", "the answer", "solution", "t-single", "t-match"):
        assert word not in html
    values = re.findall(r'<(?:input|option)[^>]*value="([^"]*)"', html)
    assert all(re.fullmatch(r"[0-9a-f]{16}|1|", v) or v.startswith(("csrf",)) for v in values if len(v) != 64), values[:5]
    assert not re.search(r'value="[A-D]"', html)


def test_real_questions_show_no_key_before_submission(client, learner):
    client.force_login(learner)
    progress.mark_studied(learner, UGC7)
    a = engine.start(learner, ut_for(UGC7))
    html = body(client.get(f"/test/attempt/{a.pk}/"))
    for uid in a.question_uids:
        q = Question.objects.get(uid=uid)
        if q.solution_html:
            assert q.solution_html not in html, uid


def test_option_order_is_shuffled_per_attempt(learner):
    progress.mark_studied(learner, UGC7)
    ut = ut_for(UGC7)
    orders = set()
    for _ in range(4):
        a = engine.start(learner, ut)
        view = engine.public_view(a)
        orders |= {tuple(o["text_html"] for o in q["options"]) for q in view}
        engine.submit(a)
    assert len(orders) == 40  # forty questions, each drawn once


def test_only_the_owner_can_see_or_answer_an_attempt(client, make_learner):
    owner, other = make_learner("owner@example.com"), make_learner("other@example.com")
    progress.mark_studied(owner, UGC7)
    a = engine.start(owner, ut_for(UGC7))
    client.force_login(other)
    for url in (f"/test/attempt/{a.pk}/", f"/test/attempt/{a.pk}/result"):
        assert client.get(url).status_code == 404
    for url in (f"/test/attempt/{a.pk}/answer", f"/test/attempt/{a.pk}/submit"):
        assert client.post(url, "{}", content_type="application/json").status_code == 404
    assert Attempt.objects.get(pk=a.pk).submitted_at is None


def test_the_whole_flow_through_the_pages(client, learner):
    client.force_login(learner)
    ut = ut_for(UGC7)
    intro = body(client.get(f"/test/{ut.unit.pk}/"))
    assert "Mark the unit done first" in intro
    progress.mark_studied(learner, UGC7)
    assert "Start the test" in body(client.get(f"/test/{ut.unit.pk}/"))
    r = client.post(f"/test/{ut.unit.pk}/start")
    a = Attempt.objects.get(user=learner)
    assert r["Location"] == f"/test/attempt/{a.pk}/"
    assert client.get(f"/test/{ut.unit.pk}/")["Location"] == f"/test/attempt/{a.pk}/"   # resume, not restart
    answers = correct_answers(a)
    r = client.post(f"/test/attempt/{a.pk}/answer", json.dumps({"question": 1, "answer": answers[1]}),
                    content_type="application/json")
    assert r.json() == {"saved": True}
    assert client.post(f"/test/attempt/{a.pk}/answer", json.dumps({"question": 11, "answer": "x"}),
                       content_type="application/json").status_code == 400
    form = {"from_form": "1"} | {f"q{n}": v for n, v in answers.items() if n > 1}
    r = client.post(f"/test/attempt/{a.pk}/submit", form)
    assert r["Location"] == f"/test/attempt/{a.pk}/result"
    result = body(client.get(r["Location"]))
    assert "10 of 10" in result and "A pass" in result and f'href="/{UGC7}"' in result
    assert result.count("the answer</span>") == 10
    assert client.post(f"/test/attempt/{a.pk}/answer", json.dumps({"question": 1, "answer": answers[1]}),
                       content_type="application/json").status_code == 409
    assert client.get(f"/test/attempt/{a.pk}/")["Location"] == f"/test/attempt/{a.pk}/result"
    dash = body(client.get("/me/"))
    assert "Your last tests" in dash and "100%" in dash


def test_the_answer_endpoint_needs_the_csrf_token(learner):
    client = Client(enforce_csrf_checks=True)
    client.force_login(learner)
    progress.mark_studied(learner, UGC7)
    a = engine.start(learner, ut_for(UGC7))
    r = client.post(f"/test/attempt/{a.pk}/answer", json.dumps({"question": 1, "answer": correct_answers(a)[1]}),
                    content_type="application/json")
    assert r.status_code == 403 and not a.responses.exists()


def test_signed_out_visitors_are_sent_to_sign_in(client):
    ut = ut_for(UGC7)
    assert client.get(f"/test/{ut.unit.pk}/")["Location"].startswith("/accounts/login/")


def test_the_unit_page_says_what_the_test_is(client, learner):
    state = lambda: json.loads(re.search(r'id="nrstat-account" type="application/json">(.*?)</script>',  # noqa: E731
                                         body(client.get("/" + UGC7))).group(1))
    guest = state()["test"]
    assert guest["n"] == 10 and guest["pass_mark"] == 70 and guest["sign_in"] == f"/accounts/login/?next=/{UGC7}"
    client.force_login(learner)
    assert state()["test"]["open"] is False
    progress.mark_studied(learner, UGC7)
    assert state()["test"]["open"] is True
    assert "test" not in json.loads(re.search(r'type="application/json">(.*?)</script>',
                                              body(client.get("/statistics/sampling-techniques/unit1.html"))).group(1))


def test_the_export_includes_every_attempt(client, learner):
    progress.mark_studied(learner, UGC7)
    engine.submit(engine.start(learner, ut_for(UGC7)))
    client.force_login(learner)
    data = json.loads(client.get("/me/export").content)
    assert data["tests"][0]["unit"] == UGC7 and data["tests"][0]["score"] == "0.00"


def test_deleting_the_account_keeps_its_attempts_anonymised(client, learner):
    from .conftest import PASSWORD
    progress.mark_studied(learner, UGC7)
    a = engine.submit(engine.start(learner, ut_for(UGC7)))
    client.force_login(learner)
    client.post("/me/delete", {"password": PASSWORD})
    a.refresh_from_db()
    assert a.user is None and a.score == 0
