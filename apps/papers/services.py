"""The papers app's interface (ARCHITECTURE.md §3): the solved papers (stored by
import_questions) and sitting them, in practice mode or as an exam (BUILD-GUIDE Step 11)."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.assessments import services as assessments
from apps.examinations import services as examinations
from apps.progress import services as progress

from .models import PaperAttempt, PaperQuestion, SolvedPaper


class PaperError(Exception):
    pass


@transaction.atomic
def store_papers(papers):
    """Upsert solved papers: [{slug, exam, title, held_on, page_path, source, duration_minutes,
    duration_source, marking_scheme, marking_source, questions: [{number, uid, official_key,
    withdrawn, withdrawn_note}]}]. Returns the number of paper questions stored."""
    n = 0
    for p in papers:
        exam = examinations.exam_by_slug(p["exam"])
        if exam is None:
            raise PaperError(f"{p['slug']}: no exam {p['exam']!r}")
        fields = {k: p.get(k) for k in ("title", "held_on", "page_path", "source", "duration_minutes",
                                         "marking_scheme")}
        fields.update(duration_source=p.get("duration_source", ""), marking_source=p.get("marking_source", ""))
        paper, _ = SolvedPaper.objects.update_or_create(slug=p["slug"], defaults=dict(fields, exam=exam))
        questions = assessments.questions_by_uid(q["uid"] for q in p["questions"])
        keep = set()
        for q in p["questions"]:
            if q["uid"] not in questions:
                raise PaperError(f"{p['slug']} Q{q['number']}: question {q['uid']} is not in the bank")
            PaperQuestion.objects.update_or_create(paper=paper, number=q["number"], defaults={
                "question": questions[q["uid"]], "official_key": q.get("official_key") or "",
                "withdrawn": q.get("withdrawn", False), "withdrawn_note": q.get("withdrawn_note", ""),
                "section": q.get("section", "")})
            keep.add(q["number"])
            n += 1
        paper.questions.exclude(number__in=keep).delete()
    return n


def paper_counts():
    return {p.slug: {"questions": p.questions.count(), "withdrawn": p.questions.filter(withdrawn=True).count()}
            for p in SolvedPaper.objects.order_by("slug")}


# ---------------------------------------------------------------- sitting a paper (BUILD-GUIDE Step 11)

PRACTICE, EXAM = "practice", "exam"
GRACE = timedelta(seconds=30)  # for an answer already on its way when the clock reaches zero
TWO = Decimal("0.01")


class Late(Exception):
    """The paper's time is up."""


def papers():
    return list(SolvedPaper.objects.select_related("exam").order_by("-held_on", "slug"))


def paper_by_slug(slug):
    return SolvedPaper.objects.select_related("exam").filter(slug=slug).first()


def paper_for_page(page_path):
    return SolvedPaper.objects.filter(page_path=page_path).first()


def rules(paper):
    """What the rules page states, each with its source, and nothing a header does not record."""
    qs = list(paper.questions.select_related("question").order_by("number"))
    doubtful = [pq for pq in qs if not pq.withdrawn and pq.question.status != "published"]
    scheme = paper.marking_scheme or {}
    return {
        "count": len(qs),
        "duration": paper.duration_minutes, "duration_source": paper.duration_source,
        "correct": Decimal(str(scheme.get("correct", 1))), "wrong": Decimal(str(scheme.get("wrong", 0))),
        "scheme_recorded": bool(scheme), "marking_source": paper.marking_source,
        "withdrawn": [pq for pq in qs if pq.withdrawn], "doubtful": doubtful,
        "counted": len(qs) - len(doubtful) - sum(1 for pq in qs if pq.withdrawn),
    }


def open_sitting(user, paper, mode):
    return (PaperAttempt.objects.select_related("attempt").filter(
        paper=paper, attempt__user=user, attempt__mode=mode, attempt__submitted_at__isnull=True).first())


@transaction.atomic
def start(user, paper, mode):
    """The learner's open sitting of this paper in this mode, or a new one. In exam
    mode the clock starts now, and only when the paper records its duration."""
    if mode not in (PRACTICE, EXAM):
        raise PaperError("Unknown mode.")
    existing = open_sitting(user, paper, mode)
    if existing:
        return existing
    uids = list(paper.questions.order_by("number").values_list("question__uid", flat=True))
    attempt = assessments.start_paper(user, uids, mode)
    deadline = None
    if mode == EXAM and paper.duration_minutes:
        deadline = attempt.started_at + timedelta(minutes=paper.duration_minutes)
    return PaperAttempt.objects.create(attempt=attempt, paper=paper, deadline=deadline)


def sitting_for(user, attempt_id):
    """A sitting, only ever its owner's (None for anyone else)."""
    s = PaperAttempt.objects.select_related("attempt", "paper").filter(attempt_id=attempt_id).first()
    return s if s and s.attempt.user_id == user.pk else None


def seconds_left(sitting):
    if not sitting.deadline:
        return None
    return max(0, int((sitting.deadline - timezone.now()).total_seconds()))


def late(sitting):
    return bool(sitting.deadline) and timezone.now() > sitting.deadline + GRACE


def _numbers(sitting):
    return list(sitting.paper.questions.order_by("number").values_list("number", flat=True))


def view(sitting):
    """The paper as the page shows it: each question with its printed number, section and,
    for one that is not counted, why. No key, no working."""
    pqs = {pq.number: pq for pq in sitting.paper.questions.all()}
    out = []
    for item, number in zip(assessments.public_view(sitting.attempt), _numbers(sitting), strict=True):
        pq = pqs[number]
        out.append(dict(item, number=number, section=pq.section, withdrawn=pq.withdrawn,
                        withdrawn_note=pq.withdrawn_note))
    return out


def answer(sitting, n, raw):
    if sitting.attempt.submitted_at:
        raise assessments.AttemptClosed("This paper has been submitted.")
    if late(sitting):
        raise Late("Time is up: answers can no longer be saved.")
    number = _numbers(sitting)[int(n) - 1] if str(n).isdigit() and 0 < int(n) <= len(_numbers(sitting)) else None
    if number is None:
        raise assessments.BadAnswer("No such question.")
    if sitting.paper.questions.filter(number=number, withdrawn=True).exists():
        raise assessments.BadAnswer("The Commission withdrew this question.")
    return assessments.save_answer(sitting.attempt, n, raw)


def reveal(sitting, n):
    """Practice mode: the key and working of one question."""
    item = assessments.reveal(sitting.attempt, n)
    if int(n) not in sitting.revealed:
        sitting.revealed = sorted(set(sitting.revealed) | {int(n)})
        sitting.save(update_fields=["revealed"])
    return item


def move(sitting, n):
    count = len(sitting.attempt.question_uids)
    sitting.position = min(max(1, int(n)), count)
    sitting.save(update_fields=["position"])
    return sitting.position


def _money(x):
    return Decimal(x).quantize(TWO, rounding=ROUND_HALF_UP)


@transaction.atomic
def submit(sitting):
    """Score and freeze. A withdrawn question, and one whose key is in doubt when the
    paper is submitted, count neither for nor against. Right answers earn the paper's
    marks, wrong ones lose what its header records (nothing, where it records none)."""
    sitting = PaperAttempt.objects.select_for_update().select_related("attempt", "paper").get(pk=sitting.pk)
    if sitting.attempt.submitted_at:
        return sitting
    r = rules(sitting.paper)
    pqs = {pq.number: pq for pq in sitting.paper.questions.select_related("question")}
    numbers = _numbers(sitting)
    score = Decimal(0)
    max_score = Decimal(0)
    not_counted = {}
    for mark, number in zip(assessments.grade(sitting.attempt), numbers, strict=True):
        pq = pqs[number]
        if pq.withdrawn:
            not_counted[str(number)] = pq.withdrawn_note
            continue
        if not mark["counts"]:
            not_counted[str(number)] = pq.question.flag_reason or "Its key is in doubt."
            continue
        max_score += r["correct"]
        if mark["answered"]:
            score += r["correct"] if mark["correct"] else r["wrong"]
    sitting.not_counted = not_counted
    sitting.save(update_fields=["not_counted"])
    assessments.close(sitting.attempt, _money(score), _money(max_score))
    if sitting.attempt.mode == EXAM:
        progress.record_paper(sitting.attempt.user, title=sitting.paper.title, slug=sitting.paper.slug,
                              score=str(_money(score)), max_score=str(_money(max_score)),
                              attempt_id=sitting.attempt.pk)
    return sitting


def sit_paper(user, slug, right, wrong):
    """Sit a paper as an exam, getting the first `right` counted questions right and the
    next `wrong` wrong, leaving the rest blank, and submit it. For demonstration data
    (setup_local) only; learners sit papers through the pages."""
    sitting = start(user, paper_by_slug(slug), EXAM)
    counted = [n for n, pq in enumerate(sitting.paper.questions.select_related("question").order_by("number"), 1)
               if not pq.withdrawn and pq.question.status == "published"]
    for i, n in enumerate(counted[:right + wrong]):
        assessments.answer_as(sitting.attempt, n, right=i < right)
    return submit(sitting)


def review(sitting):
    """After submission: the score, the totals by section, what did not count and why,
    and every question with the learner's answer, the key, the working and where it is taught."""
    r = rules(sitting.paper)
    pqs = {pq.number: pq for pq in sitting.paper.questions.select_related("question")}
    links = assessments.unit_links([pq.question.uid for pq in pqs.values()])
    items, sections = [], {}
    for item, number in zip(assessments.review_items(sitting.attempt), _numbers(sitting), strict=True):
        pq = pqs[number]
        reason = sitting.not_counted.get(str(number))
        sec = sections.setdefault(pq.section, {"name": pq.section, "right": 0, "wrong": 0, "blank": 0,
                                                "not_counted": 0, "marks": Decimal(0)})
        if reason:
            sec["not_counted"] += 1
            outcome = "not counted"
        elif not item["answered"]:
            sec["blank"] += 1
            outcome = "blank"
        elif item["correct"]:
            sec["right"] += 1
            sec["marks"] += r["correct"]
            outcome = "right"
        else:
            sec["wrong"] += 1
            sec["marks"] += r["wrong"]
            outcome = "wrong"
        items.append(dict(item, number=number, section=pq.section, outcome=outcome, reason=reason,
                          withdrawn=pq.withdrawn, study=links.get(item["uid"])))
    for sec in sections.values():
        sec["marks"] = _money(sec["marks"])
    a = sitting.attempt
    return {"items": items, "sections": list(sections.values()), "score": a.score, "max_score": a.max_score,
            "percent": assessments.percent(a.score, a.max_score) if a.max_score else Decimal(0),
            "not_counted": len(sitting.not_counted), "rules": r, "mode": a.mode}


def history(user, paper=None):
    qs = PaperAttempt.objects.select_related("attempt", "paper").filter(
        attempt__user=user, attempt__submitted_at__isnull=False)
    if paper:
        qs = qs.filter(paper=paper)
    return list(qs.order_by("-attempt__submitted_at"))
