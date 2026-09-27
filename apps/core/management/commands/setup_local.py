"""Prepare a computer to try the application offline (docs/LOCAL-CHECK.md).

Runs the migrations and both imports, then adds three local-only accounts, once.
It refuses to run unless DEBUG is on, so it can never touch a production database."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services as accounts
from apps.assessments import services as assessments
from apps.progress import services as progress

PASSWORD = "local-check-only"
OWNER = ("owner@localhost", "Owner")
NEW = ("new.learner@localhost", "Meera")
PROGRESSED = ("progress.learner@localhost", "Arjun")
STUDIED = ["statistics/descriptive-statistics/unit3.html", "exams/ugc-net/unit7.html"]


class Command(BaseCommand):
    help = "Set up this computer to try the app offline: database, content, questions and demo accounts."

    def add_arguments(self, parser):
        parser.add_argument("--skip-import", action="store_true", help="Only the accounts (the content is loaded).")

    def handle(self, *args, skip_import=False, **options):
        if not settings.DEBUG:
            raise CommandError("setup_local is for a computer you are testing on: it runs only with DEBUG on.")
        if not skip_import:
            call_command("migrate", verbosity=0)
            self.stdout.write("database: up to date")
            call_command("import_site", stdout=self.stdout)
            call_command("import_questions", stdout=self.stdout)
        made = []
        if self._account(*OWNER, staff=True):
            made.append(OWNER[0])
        if self._account(*NEW):
            made.append(NEW[0])
        user = self._account(*PROGRESSED)
        if user:
            made.append(PROGRESSED[0])
            for page in STUDIED:
                progress.mark_studied(user, page)
            assessments.sit_test(user, STUDIED[0], right=3)       # 30%: not a pass
            assessments.sit_test(user, STUDIED[1], right=10)      # 100%: the unit is passed
        self.stdout.write(self.style.SUCCESS(
            "\nReady. Open http://localhost:8000\n"
            f"  owner (admin at /staff/):   {OWNER[0]}\n"
            f"  a new learner:              {NEW[0]}\n"
            f"  a learner with progress:    {PROGRESSED[0]}\n"
            f"  password for all three:     {PASSWORD}\n"
            "Emails (sign-up, password reset) are printed here, in this window.\n"
            + (f"(created now: {', '.join(made)})" if made else "(the accounts were already there)")))

    def _account(self, email, name, staff=False):
        """Create the account if it is missing; return it only when it is new."""
        if get_user_model().objects.filter(email=email).exists():
            return None
        return accounts.create_verified_account(email, PASSWORD, name, staff=staff)
