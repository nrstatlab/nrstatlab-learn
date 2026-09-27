"""Storing the question bank (BUILD-GUIDE Step 9). Reached through assessments.services."""
import hashlib
import json

from django.db import transaction

from apps.study import services as study

from .models import Choice, Question, QuestionUnit, UnitTest


class BankError(Exception):
    """A question from a source is not fit to store. Nothing is written."""


def _hash(item):
    keep = {k: item.get(k) for k in ("qtype", "stem_html", "solution_html", "choices", "answer_text",
                                     "tolerance", "flag_reason")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def check_item(item):
    """Every key must be one of the question's own options."""
    uid, qtype, choices = item["uid"], item["qtype"], item.get("choices", [])
    labels = [c[0] for c in choices]
    if len(set(labels)) != len(labels):
        raise BankError(f"{uid}: repeated option labels {labels}")
    if item.get("flag_reason") and not item.get("scorable", True):
        return  # withdrawn: there is no key to check
    correct = [c[0] for c in choices if c[2]]
    if qtype in (Question.SINGLE, Question.ASSERTION):
        if len(correct) != 1:
            raise BankError(f"{uid}: a single-answer question needs exactly one correct option, has {correct}")
    elif qtype == Question.MULTIPLE:
        if not correct:
            raise BankError(f"{uid}: no correct option")
    elif qtype == Question.NUMERIC:
        try:
            float(item["answer_text"])
            float(item.get("tolerance") or 0)
        except (TypeError, ValueError) as e:
            raise BankError(f"{uid}: numeric key {item.get('answer_text')!r} is not a number") from e
    elif qtype == Question.MATCH:
        left = {c[0] for c in choices if c[3] == Choice.LEFT}
        right = {c[0] for c in choices if c[3] == Choice.RIGHT}
        key = json.loads(item["answer_text"])
        if set(key) != left or not set(key.values()) <= right:
            raise BankError(f"{uid}: the match key {key} does not pair the items {sorted(left)} with {sorted(right)}")
    else:
        raise BankError(f"{uid}: unknown question type {qtype!r}")


@transaction.atomic
def store_questions(items, *, prefix):
    """Upsert questions from one source. items: dicts with uid, qtype, stem_html,
    solution_html, choices [(label, html, is_correct, side)], answer_text, tolerance,
    source, source_ref, flag_reason, units [page ids], recompute_log.

    A question is published, or flagged when the source gives a reason; its status is
    set only when it is new or its content changed. Questions of this source (uid
    prefix) that the source no longer has are retired, never deleted.
    Returns {"created", "updated", "unchanged", "retired"}."""
    for item in items:
        check_item(item)
    paths = {p for item in items for p in item.get("units", [])}
    units = study.units_by_path(paths)
    missing = sorted(paths - set(units))
    if missing:
        raise BankError(f"questions link to pages that are not units: {missing[:5]}")

    counts = dict.fromkeys(("created", "updated", "unchanged", "retired"), 0)
    existing = {q.uid: q for q in Question.objects.filter(uid__startswith=prefix)}
    for item in items:
        h = _hash(item)
        q = existing.pop(item["uid"], None)
        fields = {k: item.get(k, "") for k in ("qtype", "stem_html", "solution_html", "answer_text", "source",
                                              "source_ref", "flag_reason", "recompute_log")}
        fields["tolerance"] = item.get("tolerance")
        status = Question.FLAGGED if item.get("flag_reason") else Question.PUBLISHED
        if q is None:
            q = Question.objects.create(uid=item["uid"], status=status, source_hash=h, **fields)
            counts["created"] += 1
        elif q.source_hash != h or q.status == Question.RETIRED:
            for k, v in fields.items():
                setattr(q, k, v)
            q.status, q.source_hash = status, h
            q.save()
            q.choices.all().delete()
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
            _sync_units(q, [units[p] for p in item.get("units", [])])
            continue
        Choice.objects.bulk_create([Choice(question=q, label=c[0], text_html=c[1], is_correct=c[2],
                                           side=c[3] if len(c) > 3 else "", order=i)
                                    for i, c in enumerate(item["choices"])])
        _sync_units(q, [units[p] for p in item.get("units", [])])
    for gone in existing.values():
        if gone.status != Question.RETIRED:
            gone.status = Question.RETIRED
            gone.save(update_fields=["status", "updated_at"])
            counts["retired"] += 1
    for unit in units.values():
        UnitTest.objects.get_or_create(unit=unit)
    return counts


def _sync_units(q, units):
    want = {u.pk for u in units}
    have = set(q.unit_links.values_list("unit_id", flat=True))
    QuestionUnit.objects.filter(question=q, unit_id__in=have - want).delete()
    QuestionUnit.objects.bulk_create([QuestionUnit(question=q, unit_id=u) for u in want - have])


def bank_counts(prefix=""):
    qs = Question.objects.filter(uid__startswith=prefix)
    return {s: qs.filter(status=s).count() for s, _ in Question.STATUSES} | {"total": qs.count()}
