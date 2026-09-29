"""Counts of what the database holds, to compare before a backup and after a restore
(docs/LOCAL-CHECK.md, 7.2; docs/DEPLOY.md, "Backups")."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.assessments import services as assessments
from apps.examinations import services as examinations
from apps.progress import services as progress
from apps.study import services as study


class Command(BaseCommand):
    help = "Print counts of accounts, progress, attempts, questions and pages: compare them after a restore."

    def handle(self, *args, **options):
        rows = {"accounts": get_user_model().objects.count(), **progress.counts(), **assessments.counts(),
                **study.stored_counts(),
                "syllabus items": sum(c["items"] for c in examinations.syllabus_counts().values())}
        width = max(len(k) for k in rows)
        for k, v in rows.items():
            self.stdout.write(f"{k:<{width}}  {v}")
