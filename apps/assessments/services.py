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
