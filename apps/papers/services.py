"""The papers app's interface (ARCHITECTURE.md §3). Phase 3 stores the solved papers
and their questions; practice and exam mode arrive in Phase 4."""
from django.db import transaction

from apps.assessments import services as assessments
from apps.examinations import services as examinations

from .models import PaperQuestion, SolvedPaper


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
                "withdrawn": q.get("withdrawn", False), "withdrawn_note": q.get("withdrawn_note", "")})
            keep.add(q["number"])
            n += 1
        paper.questions.exclude(number__in=keep).delete()
    return n


def paper_counts():
    return {p.slug: {"questions": p.questions.count(), "withdrawn": p.questions.filter(withdrawn=True).count()}
            for p in SolvedPaper.objects.order_by("slug")}
