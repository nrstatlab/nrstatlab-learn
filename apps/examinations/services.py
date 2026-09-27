"""The examinations app's interface (ARCHITECTURE.md §3)."""
from .models import Exam


def store_exams(exams):
    """Upsert the exams: [{"slug", "name", "hub_path", "order"}]."""
    for e in exams:
        Exam.objects.update_or_create(slug=e["slug"], defaults={k: v for k, v in e.items() if k != "slug"})


def exam_count():
    return Exam.objects.count()


def exam_by_slug(slug):
    return Exam.objects.filter(slug=slug).first()
