from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Fast hashing in tests only; production uses Argon2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AXES_ENABLED = False
# collectstatic output does not exist in tests; the app's own static files are found directly.
STATIC_ROOT = None
WHITENOISE_USE_FINDERS = True
