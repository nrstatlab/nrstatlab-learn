"""Settings shared by every environment. Everything secret or host-specific comes
from the environment (see .env.example); nothing secret is ever written here."""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# The static site this application serves: a git submodule, never edited here.
CONTENT_DIR = Path(env("CONTENT_DIR", default=str(BASE_DIR / "content")))
# Non-HTML site files (CSS, images, PDFs) copied by import_site, served at their old paths.
SITE_ROOT_DIR = Path(env("SITE_ROOT_DIR", default=str(BASE_DIR / "var" / "site_root")))
# The public origin every canonical URL is written against. Until the new domain
# exists this is the current site, so rendered pages stay identical to it.
SITE_ORIGIN = env("SITE_ORIGIN", default="https://nrstatlab.github.io/planning-for-future").rstrip("/")
# The path the site is served under on SITE_ORIGIN's host. The app serves it at the root.
SITE_BASE_PATH = env("SITE_BASE_PATH", default="/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "apps.core",
    "apps.accounts",
    "apps.study",
    "apps.examinations",
    "apps.papers",
    "apps.assessments",
    "apps.progress",
]
SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# allauth: email is the login; verification is mandatory (wired up in Phase 2).
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# django-axes: lock an account/IP pair after 5 failures, for an hour.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# The site's own files are served at their original paths from SITE_ROOT_DIR.
# Nothing ending in .html is ever copied there, so every page still goes through Django.
WHITENOISE_ROOT = SITE_ROOT_DIR

# Unit test defaults (decided 26 September 2026; ARCHITECTURE.md §1, decision 6).
UNIT_TEST_QUESTIONS = 10
UNIT_TEST_PASS_MARK = 70
