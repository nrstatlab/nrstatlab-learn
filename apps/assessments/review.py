"""The reviewer workflow (BUILD-GUIDE Step 13, decision 8) and every question's history.

A reviewer is a member of the "Reviewers" group (or a superuser). Approving publishes a
question and records who reviewed it; it is refused when the reviewer is the question's
author, so no one approves their own work. Sending back needs a note, and returns the
question to draft. Every change is recorded as a QuestionEvent.
"""
from django.db import transaction
from django.utils import timezone

from .models import ItemStats, Question, QuestionEvent

REVIEWERS = "Reviewers"


class ReviewRefused(Exception):
    pass


def is_reviewer(user):
    return bool(user and user.is_active and user.is_staff
                and (user.is_superuser or user.groups.filter(name=REVIEWERS).exists()))


def reviewers():
    from django.contrib.auth import get_user_model

    return list(get_user_model().objects.filter(is_active=True, groups__name=REVIEWERS).exclude(email=""))


def record(question, action, *, user=None, from_status="", to_status="", note="", changes=None):
    return QuestionEvent.objects.create(question=question, action=action, user=user, from_status=from_status,
                                        to_status=to_status, note=note, changes=changes or {})


def history(question):
    return list(question.events.select_related("user").order_by("at", "pk"))


@transaction.atomic
def approve(question, user, note=""):
    """Publish the question, as reviewed by user."""
    if not is_reviewer(user):
        raise ReviewRefused("Only a reviewer can approve a question.")
    q = Question.objects.select_for_update().get(pk=question.pk)
    if q.author_id and q.author_id == user.pk:
        raise ReviewRefused("You wrote this question, so another reviewer must approve it.")
    if q.status == Question.RETIRED:
        raise ReviewRefused("A retired question cannot be approved.")
    if not q.answer_text and not q.choices.filter(is_correct=True).exists():
        raise ReviewRefused("It has no key (withdrawn, or not yet keyed), so it cannot be published.")
    before, reason = q.status, q.flag_reason
    q.status, q.reviewer, q.reviewed_at = Question.PUBLISHED, user, timezone.now()
    q.flag_reason = ""
    q.save(update_fields=["status", "reviewer", "reviewed_at", "flag_reason", "updated_at"])
    # the statistics that flagged it have now been looked at: only new evidence flags it again
    ItemStats.objects.filter(question=q).update(cleared_at_n=_stats_n(q))
    record(q, QuestionEvent.APPROVED, user=user, from_status=before, to_status=q.status, note=note.strip(),
           changes={"flag_reason": [reason, ""]} if reason else None)
    return q


def _stats_n(q):
    stats = ItemStats.objects.filter(question=q).first()
    return stats.n if stats else None


@transaction.atomic
def send_back(question, user, note):
    """Return the question to draft, with the reviewer's note."""
    if not is_reviewer(user):
        raise ReviewRefused("Only a reviewer can send a question back.")
    note = (note or "").strip()
    if not note:
        raise ReviewRefused("Say what needs changing: a note is required to send a question back.")
    q = Question.objects.select_for_update().get(pk=question.pk)
    before = q.status
    q.status, q.flag_reason = Question.DRAFT, f"Sent back: {note}"
    q.save(update_fields=["status", "flag_reason", "updated_at"])
    record(q, QuestionEvent.SENT_BACK, user=user, from_status=before, to_status=q.status, note=note)
    return q
