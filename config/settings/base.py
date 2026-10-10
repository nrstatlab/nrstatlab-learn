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
    "csp",
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
    "csp.middleware.CSPMiddleware",
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

# The Content Security Policy (BUILD-GUIDE Step 16), everywhere, the laptop included. The
# application's pages run scripts from this origin only; a page of the site adds exactly
# what it needs itself (apps/core/csp.py). MathJax is served from here, and adds styles.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        # allauth's Google sign-in posts here, then redirects to Google
        "form-action": ["'self'", "https://accounts.google.com"],
    },
}
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
                "apps.core.context.learn",
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

# allauth: email is the login; verification is mandatory. Sign-up, by email or by
# Google, always goes through accounts.forms.SignupForm (name, 18 and over, privacy).
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.SignupForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "StatsTricks360: "
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/me/"
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_STORE_TOKENS = False
# Google sign-in appears only when its OAuth client is configured (BUILD-GUIDE Step 7).
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET}]
        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET else [],
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    },
}

# Email goes through whatever EMAIL_URL names (smtp+tls://…, or consolemail:// in
# development); the provider is chosen before staging (ARCHITECTURE.md §9.2).
EMAIL_CONFIG = env.email_url("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="StatsTricks360 <no-reply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# django-axes: lock an account/IP pair after 5 failures, for an hour. Only failed
# attempts are recorded; successful logins are not logged (the privacy page says so).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_USERNAME_CALLABLE = "apps.accounts.lockout.username"
AXES_DISABLE_ACCESS_LOG = True
AXES_RESET_ON_SUCCESS = True
# While locked out, say so (a 429 page) rather than "wrong password"; the hour is not extended.
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False
# While locked out, say so (a 429 page), rather than "wrong password"; the hour is not extended.

# The admin needs a TOTP device when this is on (default in production).
ADMIN_OTP_REQUIRED = env.bool("ADMIN_OTP_REQUIRED", default=False)
OTP_TOTP_ISSUER = "StatsTricks360"

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
