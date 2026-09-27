"""Production. Hardened settings from BUILD-GUIDE Step 16; completed in Phase 7."""
from .base import *  # noqa: F401,F403

DEBUG = False
ADMIN_OTP_REQUIRED = env.bool("ADMIN_OTP_REQUIRED", default=True)  # noqa: F405
EMAIL_CONFIG = env.email_url("EMAIL_URL")  # noqa: F405  (required in production)
vars().update(EMAIL_CONFIG)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
