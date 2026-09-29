"""The examinations app's interface (ARCHITECTURE.md §3)."""
from apps.study import services as study

from .models import Exam, ExamPaper, SyllabusItem, SyllabusLink
from .readiness import clear_target, readiness, set_target, summary, target_of  # noqa: F401
from .readiness import export as export_target  # noqa: F401


def store_exams(exams):
    """Upsert the exams: [{"slug", "name", "hub_path", "order"}]."""
    for e in exams:
        Exam.objects.update_or_create(slug=e["slug"], defaults={k: v for k, v in e.items() if k != "slug"})


def exam_count():
    return Exam.objects.count()


def exam_by_slug(slug):
    return Exam.objects.filter(slug=slug).first()


def exams():
    return list(Exam.objects.all())


def store_syllabus(syllabus):
    """Store each exam's map: {slug: [{"code", "title", "items": [{"code", "text", "grade",
    "links": [(path, depth)]}]}]} (apps/core/syllabus.py). Upserts, so an unchanged map
    changes nothing; an item or group the map no longer has is deleted with its links,
    as they hold no learner data. Returns {"created", "updated", "unchanged", "deleted"}."""
    counts = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    paths = {p for groups in syllabus.values() for g in groups for i in g["items"] for p, _ in i["links"]}
    units = study.units_by_path(paths)
    for slug, groups in syllabus.items():
        exam = Exam.objects.get(slug=slug)
        keep_items, keep_papers = [], []
        order = 0
        for gi, g in enumerate(groups):
            paper, _ = ExamPaper.objects.update_or_create(
                exam=exam, code=g["code"], defaults={"title": g["title"], "order": gi})
            keep_papers.append(paper.pk)
            for it in g["items"]:
                order += 1
                wanted = {"paper_id": paper.pk, "text": it["text"], "grade": it["grade"], "order": order}
                links = sorted((p, d, units[p].pk if p in units else None) for p, d in it["links"])
                item = SyllabusItem.objects.filter(exam=exam, code=it["code"]).first()
                if item is None:
                    item = SyllabusItem.objects.create(exam=exam, code=it["code"], **wanted)
                    counts["created"] += 1
                else:
                    have = sorted(item.links.values_list("target_path", "depth", "unit_id"))
                    if all(getattr(item, k) == v for k, v in wanted.items()) and have == links:
                        counts["unchanged"] += 1
                        keep_items.append(item.pk)
                        continue
                    for k, v in wanted.items():
                        setattr(item, k, v)
                    item.save()
                    item.links.all().delete()
                    counts["updated"] += 1
                SyllabusLink.objects.bulk_create(
                    SyllabusLink(item=item, target_path=p, depth=d, unit_id=u) for p, d, u in links)
                keep_items.append(item.pk)
        gone = SyllabusItem.objects.filter(exam=exam).exclude(pk__in=keep_items)
        counts["deleted"] += gone.count()
        gone.delete()
        ExamPaper.objects.filter(exam=exam).exclude(pk__in=keep_papers).delete()
    return counts


def syllabus_counts():
    """{exam slug: {"items", "with a unit", "page only", "not here"}}, as stored."""
    out = {e.slug: {"items": 0, "with a unit": 0, "page only": 0, "not here": 0} for e in Exam.objects.all()}
    for item in SyllabusItem.objects.select_related("exam").prefetch_related("links"):
        links = list(item.links.all())
        c = out[item.exam.slug]
        c["items"] += 1
        c["with a unit" if any(link.unit_id for link in links) else "page only" if links else "not here"] += 1
    return out


def dashboard_card(user):
    """The readiness card on the dashboard (registered with progress in apps.py)."""
    exam = target_of(user)
    return {"template": "examinations/card.html", "summary": summary(user, exam) if exam else None}
