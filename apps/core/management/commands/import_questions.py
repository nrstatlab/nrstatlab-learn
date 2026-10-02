from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessments import services as assessments
from apps.core import questions
from apps.papers import services as papers


class Command(BaseCommand):
    help = "Load the question bank and the solved papers from content/ (BUILD-GUIDE Step 9). Run after import_site."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Read and check the sources; write nothing.")

    def handle(self, *args, dry_run=False, **options):
        try:
            bank = questions.read_bank(settings.CONTENT_DIR)
            for prefix, items in bank.sources.items():
                for item in items:
                    assessments.check_item(item)
                if len(items) != bank.expected[prefix]:
                    raise CommandError(f"{prefix}: read {len(items)} questions, the source states {bank.expected[prefix]}")
        except (ValueError, assessments.BankError) as e:
            raise CommandError(str(e)) from e
        for prefix, items in bank.sources.items():
            unscorable = sum(1 for i in items if not i.get("scorable", True))
            flagged = sum(1 for i in items if i["flag_reason"] and i.get("scorable", True))
            linked = sum(1 for i in items if i["units"])
            self.stdout.write(f"read {prefix}: {len(items)} questions (as the source states), "
                              f"{flagged} flagged, {unscorable} never scored, {linked} linked to a unit")
        if dry_run:
            self.stdout.write("dry run: nothing written")
            return
        try:
            with transaction.atomic():
                for prefix, items in bank.sources.items():
                    c = assessments.store_questions(items, prefix=prefix)
                    self.stdout.write(f"{prefix}: {c['created']} created, {c['updated']} updated, "
                                      f"{c['unchanged']} unchanged, {c['retired']} retired")
                    stored = assessments.bank_counts(prefix)
                    live = stored["total"] - stored["retired"]
                    scorable = sum(1 for i in items if i.get("scorable", True))  # the rest are stored retired
                    if live != scorable:
                        raise CommandError(f"{prefix}: {live} stored, {scorable} read -- nothing was committed")
                n = papers.store_papers(bank.papers)
        except (assessments.BankError, papers.PaperError) as e:
            raise CommandError(f"{e} -- nothing was committed") from e
        self.stdout.write(self.style.SUCCESS(f"papers: {len(bank.papers)} solved papers, {n} paper questions"))
