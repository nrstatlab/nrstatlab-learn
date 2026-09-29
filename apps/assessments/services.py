"""The assessments app's interface (ARCHITECTURE.md §3): the question bank and the
unit test engine. Other apps use only these names."""
from .bank import BankError, bank_counts, check_item, store_questions  # noqa: F401
from .engine import (  # noqa: F401
    AttemptClosed,
    BadAnswer,
    TestLocked,
    availability,
    close,
    export,
    grade,
    percent,
    public_view,
    reveal,
    review_items,
    save_answer,
    start_paper,
    test_for_unit,
)
from .models import Question
from .review import ReviewRefused, approve, history, is_reviewer, record, send_back  # noqa: F401
from .stats import run as item_stats  # noqa: F401


def questions_by_uid(uids):
    return {q.uid: q for q in Question.objects.filter(uid__in=list(uids))}


def tested_units(paths):
    """The page ids, among these, of units whose test is open to take: the unit has a
    test and enough published questions for it (engine.test_for_unit, in bulk)."""
    from django.db.models import Count, F, Q

    from .models import UnitTest

    return set(UnitTest.objects.filter(unit__legacy_path__in=list(paths))
               .annotate(published=Count("unit__question_links__question", distinct=True,
                                         filter=Q(unit__question_links__question__status=Question.PUBLISHED)))
               .filter(published__gte=F("n_questions"))
               .values_list("unit__legacy_path", flat=True))


def sit_test(user, page_id, right):
    """Take the unit's test as a learner who gets `right` questions right, and submit it.
    For demonstration data (setup_local) only; learners sit tests through the pages.
    Returns the submitted attempt."""
    from . import engine
    from .models import UnitTest

    attempt = engine.start(user, UnitTest.objects.get(unit__legacy_path=page_id))
    for n in range(1, len(attempt.question_uids) + 1):
        answer_as(attempt, n, right=n <= right)
    return engine.submit(attempt)


def answer_as(attempt, n, right):
    """Save question n's answer as a learner who gets it right, or wrong (a single or
    multiple choice question). For demonstration data (setup_local) only."""
    import json

    from . import engine

    uid = attempt.question_uids[n - 1]
    q = Question.objects.prefetch_related("choices").get(uid=uid)
    if q.qtype == Question.MATCH:
        key = json.loads(q.answer_text)
        raw = {k: engine.token(attempt, uid, "right", v) for k, v in key.items()}
    elif q.qtype == Question.NUMERIC:
        raw = q.answer_text
    else:
        wanted = [c for c in q.choices.all() if c.is_correct == right and not c.side]
        raw = engine.token(attempt, uid, "option", wanted[0].label)
    return engine.save_answer(attempt, n, raw)


def unit_links(uids):
    """{question uid: {"title", "path"}}: the unit that teaches each question, where one is linked."""
    from .models import QuestionUnit

    out = {}
    for uid, title, path in QuestionUnit.objects.filter(question__uid__in=list(uids)).values_list(
            "question__uid", "unit__title", "unit__legacy_path").order_by("question__uid", "unit__order"):
        out.setdefault(uid, {"title": title, "path": path})
    return out


# ---------------------------------------------------------------- demonstration data (setup_local only)

def add_to_reviewers(user):
    from django.contrib.auth.models import Group

    user.groups.add(Group.objects.get(name="Reviewers"))


def demo_draft(author):
    """A draft question by `author`, so the two-person rule can be tried: its author
    cannot approve it, and another reviewer can. It links to no unit, so it is never
    drawn even once published."""
    from .models import Choice, QuestionEvent

    q, made = Question.objects.get_or_create(uid="local-demo-draft-001", defaults={
        "stem_html": "<p>The median of 3, 8, 5, 12, 7 is</p>", "status": Question.DRAFT, "author": author,
        "solution_html": "<p>In order: 3, 5, 7, 8, 12. The middle value is 7.</p>",
        "source": "local demonstration (setup_local)", "recompute_log": "Sorted by hand: 3, 5, 7, 8, 12 -> 7."})
    if made:
        Choice.objects.bulk_create([Choice(question=q, label=lab, text_html=t, is_correct=lab == "C", order=i)
                                    for i, (lab, t) in enumerate([("A", "5"), ("B", "8"), ("C", "7"), ("D", "12")])])
        record(q, QuestionEvent.IMPORTED, user=author, to_status=Question.DRAFT, note="Written for the local check.")
    return q


def demo_item_data(page_id, attempts=40):
    """Submitted, anonymous sittings of a unit's test, answered to a known pattern, so
    that `item_stats` has figures to show: nine questions that the abler sitters get
    right more often, and one planted the other way round (a negative r_pb), which the
    statistics flag. Returns the planted question's uid."""
    from django.utils import timezone

    from . import engine
    from .models import Attempt, Response, UnitTest

    ut = UnitTest.objects.get(unit__legacy_path=page_id)
    uids = [q.uid for q in engine.pool(ut)[:10]]
    qs = questions_by_uid(uids)
    planted = uids[-1]
    thresholds = [0.15 + j * 0.0875 for j in range(9)]
    for i in range(attempts):
        ability = i / (attempts - 1)
        right = [ability > t for t in thresholds] + [ability < 0.5]
        a = Attempt.objects.create(user=None, kind=Attempt.UNIT_TEST, unit_test=ut, seed=i, question_uids=uids,
                                   submitted_at=timezone.now(), score=sum(right), max_score=len(uids))
        Response.objects.bulk_create(Response(attempt=a, question=qs[uid], answer="demo", correct=ok)
                                     for uid, ok in zip(uids, right, strict=True))
    return planted
