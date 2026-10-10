"""Item analysis (BUILD-GUIDE Step 13), run nightly by `manage.py item_stats`.

For each question with 30 or more responses on submitted attempts:

    p    = correct / n
    R    = the attempt's rest-score: the share of its other counted answers that are right
    M1, M0 = the mean R of those who answered this question right, and wrong
    s    = the standard deviation of R, with n in the denominator
    r_pb = (M1 - M0) / s * sqrt(p (1 - p))

The owner's decisions: the attempts are unit tests and old papers sat in exam mode (not
practice, where answers can be revealed), and R is a share, so a ten-question unit test
and a 150-question paper are on the same scale. A response counts when it was marked
right or wrong: a blank is not a response, and a question that did not count in that
attempt (withdrawn, or its key in doubt) is left out.

A published question is flagged for review when r_pb < 0, p > 0.95 or p < 0.10, and the
reviewers are told. A question a reviewer has approved since is flagged again only on 30
more responses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q

from . import review
from .models import Attempt, ItemStats, Question, QuestionEvent, Response

MIN_RESPONSES = 30
RENEW_AFTER = 30          # more responses before an approved question is flagged again
P_HIGH, P_LOW = 0.95, 0.10


@dataclass
class Figures:
    n: int
    p: float
    r_pb: float | None      # None when it cannot be computed: s = 0, or p is 0 or 1


def figures(pairs):
    """pairs: [(correct, rest_score)] for one question. p and r_pb, as defined above."""
    n = len(pairs)
    right = [r for ok, r in pairs if ok]
    wrong = [r for ok, r in pairs if not ok]
    p = len(right) / n
    mean = sum(r for _, r in pairs) / n
    s = math.sqrt(sum((r - mean) ** 2 for _, r in pairs) / n)
    if not right or not wrong or s == 0:
        return Figures(n, p, None)
    m1, m0 = sum(right) / len(right), sum(wrong) / len(wrong)
    return Figures(n, p, (m1 - m0) / s * math.sqrt(p * (1 - p)))


def reasons(f):
    out = []
    if f.r_pb is not None and f.r_pb < 0:
        out.append(f"r_pb is negative ({f.r_pb:.3f}): those who got it right did worse on the rest")
    if f.p > P_HIGH:
        out.append(f"p is above {P_HIGH:.2f} ({f.p:.3f}): almost everyone gets it right")
    if f.p < P_LOW:
        out.append(f"p is below {P_LOW:.2f} ({f.p:.3f}): almost no one gets it right")
    return out


def eligible_attempts():
    return Attempt.objects.filter(submitted_at__isnull=False).filter(
        Q(kind=Attempt.UNIT_TEST) | Q(kind=Attempt.PAPER, mode="exam"))


def collect():
    """{question id: [(correct, rest_score)]} from every counted response on the eligible
    attempts. An attempt with fewer than two counted answers has no rest-score."""
    rows = list(Response.objects.filter(attempt__in=eligible_attempts(), correct__isnull=False)
                .values_list("attempt_id", "question_id", "correct"))
    per_attempt = {}
    for attempt_id, _, ok in rows:
        right, total = per_attempt.get(attempt_id, (0, 0))
        per_attempt[attempt_id] = (right + ok, total + 1)
    out = {}
    for attempt_id, question_id, ok in rows:
        right, total = per_attempt[attempt_id]
        if total < 2:
            continue
        out.setdefault(question_id, []).append((ok, (right - ok) / (total - 1)))
    return out


def run(notify=True):
    """Compute and store the figures; flag what needs a reviewer. Returns a summary."""
    data = collect()
    summary = {"questions": 0, "flagged": []}
    with transaction.atomic():
        for question_id, pairs in data.items():
            if len(pairs) < MIN_RESPONSES:
                continue
            f = figures(pairs)
            summary["questions"] += 1
            stats, _ = ItemStats.objects.update_or_create(
                question_id=question_id, defaults={"n": f.n, "difficulty": f.p, "point_biserial": f.r_pb})
            why = reasons(f)
            if not why:
                continue
            q = Question.objects.select_for_update().get(pk=question_id)
            if q.status != Question.PUBLISHED:
                continue                         # already with the reviewers, or not in use
            if stats.cleared_at_n is not None and f.n < stats.cleared_at_n + RENEW_AFTER:
                continue                         # a reviewer approved it on this evidence
            rpb = "not defined" if f.r_pb is None else f"{f.r_pb:.3f}"
            reason = f"Item statistics (n = {f.n}, p = {f.p:.3f}, r_pb = {rpb}): " + "; ".join(why) + "."
            q.status, q.flag_reason = Question.FLAGGED, reason
            q.save(update_fields=["status", "flag_reason", "updated_at"])
            review.record(q, QuestionEvent.STATS_FLAGGED, from_status=Question.PUBLISHED,
                          to_status=Question.FLAGGED, note=reason)
            summary["flagged"].append((q.uid, reason))
    if notify and summary["flagged"]:
        summary["told"] = tell_reviewers(summary["flagged"])
    return summary


def tell_reviewers(flagged):
    """One email to the reviewers, listing what the statistics flagged."""
    to = [u.email for u in review.reviewers()]
    if not to:
        return []
    lines = [f"- {uid}: {reason}" for uid, reason in flagged]
    body = ("The nightly item statistics flagged these questions for review. They are out of every test "
            "until a reviewer approves or sends them back, in the review queue at /staff/assessments/reviewquestion/.\n\n"
            + "\n".join(lines) + "\n")
    send_mail(f"[StatsTricks360] {len(flagged)} question{'s' if len(flagged) != 1 else ''} flagged for review",
              body, settings.DEFAULT_FROM_EMAIL, to)
    return to
