from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from django.conf import settings
        from django.contrib import admin
        from django_otp.admin import OTPAdminSite

        if settings.ADMIN_OTP_REQUIRED:
            # Staff sign in to /staff/ with a password and a TOTP code (BUILD-GUIDE Step 16).
            admin.site.__class__ = OTPAdminSite
