from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Give a staff member a TOTP device for the admin, and print its otpauth:// URI once."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--name", default="authenticator")

    def handle(self, email, name, **options):
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None or not user.is_staff:
            raise CommandError(f"No staff member with the email {email}")
        device = TOTPDevice.objects.create(user=user, name=name, confirmed=True)
        self.stdout.write("Scan this into an authenticator app, then clear the terminal:")
        self.stdout.write(device.config_url)
