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
