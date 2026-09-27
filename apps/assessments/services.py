"""The assessments app's interface (ARCHITECTURE.md §3): the question bank and the
unit test engine. Other apps use only these names."""
from .bank import BankError, bank_counts, check_item, store_questions  # noqa: F401
from .engine import (  # noqa: F401
    AttemptClosed,
    BadAnswer,
    TestLocked,
    availability,
    export,
    percent,
    test_for_unit,
)
from .models import Question


def questions_by_uid(uids):
    return {q.uid: q for q in Question.objects.filter(uid__in=list(uids))}


def sit_test(user, page_id, right):
    """Take the unit's test as a learner who gets `right` questions right, and submit it.
    For demonstration data (setup_local) only; learners sit tests through the pages.
    Returns the submitted attempt."""
    import json

    from . import engine
    from .models import UnitTest

    attempt = engine.start(user, UnitTest.objects.get(unit__legacy_path=page_id))
    for n, uid in enumerate(attempt.question_uids, 1):
        q = Question.objects.prefetch_related("choices").get(uid=uid)
        if q.qtype == Question.MATCH:
            key = json.loads(q.answer_text)
            raw = {k: engine.token(attempt, uid, "right", v) for k, v in key.items()}
        elif q.qtype == Question.NUMERIC:
            raw = q.answer_text
        else:
            wanted = [c for c in q.choices.all() if c.is_correct == (n <= right) and not c.side]
            raw = engine.token(attempt, uid, "option", wanted[0].label)
        engine.save_answer(attempt, n, raw)
    return engine.submit(attempt)
