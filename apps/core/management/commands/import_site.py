from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import importer


class Command(BaseCommand):
    help = "Load the static site in content/ into the database and copy its files (BUILD-GUIDE Step 5)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Read and check the content; write nothing.")
        parser.add_argument("--files-only", action="store_true",
                            help="Only copy the non-HTML site files (used by the Docker build; no database).")

    def handle(self, *args, dry_run=False, files_only=False, **options):
        try:
            src = importer.Source.read(settings.CONTENT_DIR)
            src.check()
        except importer.ImportError_ as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            f"read: {len(src.courses)} courses, {len(src.markable)} markable units, "
            f"{len(src.indexed)} indexed pages, {len(src.pages) - len(src.indexed)} other pages, "
            f"{len(src.stubs)} redirects, {len(src.exams)} exams, {len(src.site_files)} site files")
        from apps.core import syllabus
        for slug, groups in src.syllabus.items():
            c = syllabus.counts(groups, src.markable)
            self.stdout.write(f"read {slug} syllabus: {c['items']} items; {c['with a unit']} taught in a unit, "
                              f"{c['page only']} only on pages with nothing to mark, {c['not here']} not here")
        if dry_run:
            self.stdout.write("dry run: nothing written")
            return
        files = importer.copy_site_files(src, settings.SITE_ROOT_DIR)
        self.stdout.write(f"site files: {files['copied']} copied, {files['unchanged']} unchanged")
        if files_only:
            return
        try:
            with transaction.atomic():
                counts = importer.write_database(src)
                stored = importer.verify_database(src)
        except importer.ImportError_ as e:
            raise CommandError(f"{e} -- nothing was committed") from e
        self.stdout.write(f"pages: {counts['created']} created, {counts['updated']} updated, "
                          f"{counts['unchanged']} unchanged, {counts['deleted']} deleted")
        sy = counts["syllabus"]
        self.stdout.write(f"syllabus items: {sy['created']} created, {sy['updated']} updated, "
                          f"{sy['unchanged']} unchanged, {sy['deleted']} deleted")
        self.stdout.write(self.style.SUCCESS("stored: " + ", ".join(f"{v} {k}" for k, v in stored.items())))
