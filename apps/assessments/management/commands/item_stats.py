from django.core.management.base import BaseCommand

from apps.assessments import stats


class Command(BaseCommand):
    help = ("Item analysis (BUILD-GUIDE Step 13): p and the point-biserial r_pb for every question with "
            f"{stats.MIN_RESPONSES} or more responses; flag for review and tell the reviewers. Run nightly.")

    def add_arguments(self, parser):
        parser.add_argument("--no-email", action="store_true", help="Flag, but do not email the reviewers.")

    def handle(self, *args, no_email=False, **options):
        summary = stats.run(notify=False)
        self.stdout.write(f"item statistics: {summary['questions']} question(s) with {stats.MIN_RESPONSES} "
                          f"or more responses; {len(summary['flagged'])} flagged for review")
        for uid, reason in summary["flagged"]:
            self.stdout.write(f"  {uid}: {reason}")
        if summary["flagged"] and not no_email:
            told = stats.tell_reviewers(summary["flagged"])
            self.stdout.write(f"reviewers told: {', '.join(told)}" if told else
                              self.style.WARNING("no one is in the Reviewers group: nobody was emailed"))
