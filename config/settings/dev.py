from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1"]  # noqa: F405
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
STATIC_ROOT = None
WHITENOISE_USE_FINDERS = True
