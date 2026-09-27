"""Accounts (BUILD-GUIDE Step 7): sign-up for adults, verified email, Google only
when configured, lockout, the data export, deletion, and the admin's second factor."""
import json

import pytest
from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.sites.models import Site
from django.core import mail
from django.core.management import call_command
from django.test import override_settings

from apps.accounts.models import Profile, User
from apps.assessments.models import Attempt
from apps.progress import services as progress
from apps.progress.models import ActivityEvent, UnitProgress

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db
SIGNUP = {"display_name": "  Ravi   Kumar ", "email": "ravi@example.com", "password1": "correct-horse-battery",
          "password2": "correct-horse-battery", "age_confirmed": "on", "privacy_read": "on"}


@pytest.mark.parametrize("missing", ["display_name", "age_confirmed", "privacy_read"])
def test_signup_requires_a_name_18_plus_and_the_privacy_notice(client, missing):
    data = {k: v for k, v in SIGNUP.items() if k != missing}
    r = client.post("/accounts/signup/", data)
    assert r.status_code == 200 and "This field is required" in r.content.decode()
    assert not User.objects.exists()


def test_signup_creates_a_profile_and_sends_a_verification_email(client):
    r = client.post("/accounts/signup/", SIGNUP)
    assert r.status_code == 302
    user = User.objects.get(email="ravi@example.com")
    assert (user.profile.display_name, user.profile.age_confirmed) == ("Ravi Kumar", True)
    assert user.profile.terms_accepted_at is not None
    assert not user.profile.browser_import_done
    [message] = mail.outbox
    assert message.to == ["ravi@example.com"] and "/accounts/confirm-email/" in message.body
    assert "example.com" not in message.subject and message.subject.startswith("NRSTATLAB: ")


def test_signup_form_shows_the_privacy_link(client):
    body = client.get("/accounts/signup/").content.decode()
    assert 'href="/privacy.html"' in body and "I am 18 or over" in body


def test_login_is_refused_until_the_email_is_verified(client, django_user_model):
    user = django_user_model.objects.create_user("new@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    r = client.post("/accounts/login/", {"login": user.email, "password": PASSWORD})
    assert "_auth_user_id" not in client.session
    assert r.status_code == 302 and "confirm-email" in r["Location"]
    EmailAddress.objects.filter(user=user).update(verified=True)
    r = client.post("/accounts/login/", {"login": user.email, "password": PASSWORD})
    assert client.session["_auth_user_id"] == str(user.pk) and r["Location"] == "/me/"


def test_login_returns_to_the_page_it_came_from(client, learner):
    r = client.post("/accounts/login/?next=/statistics/sampling-theory/unit2.html",
                    {"login": learner.email, "password": PASSWORD, "next": "/statistics/sampling-theory/unit2.html"})
    assert r["Location"] == "/statistics/sampling-theory/unit2.html"


def test_google_appears_only_when_configured(client):
    assert "/accounts/google/login/" not in client.get("/accounts/login/").content.decode()
    providers = {"google": {"APPS": [{"client_id": "id", "secret": "s"}], "SCOPE": ["email", "profile"]}}
    with override_settings(SOCIALACCOUNT_PROVIDERS=providers):
        assert "/accounts/google/login/" in client.get("/accounts/login/").content.decode()


@override_settings(AXES_ENABLED=True)
def test_the_sixth_attempt_after_five_failures_is_locked_out(client, learner):
    """django-axes locks the account from this address at the fifth failure (a 429);
    allauth's own limit on failed sign-ins then answers first, with its message.
    Either way the right password does not get in."""
    codes = [client.post("/accounts/login/", {"login": learner.email, "password": "wrong-password"}).status_code
             for _ in range(5)]
    assert codes == [200, 200, 200, 200, 429]
    r = client.post("/accounts/login/", {"login": learner.email, "password": PASSWORD})
    assert "_auth_user_id" not in client.session
    assert r.status_code == 429 or "Too many failed login attempts" in r.content.decode()
    from axes.models import AccessAttempt
    assert AccessAttempt.objects.get().username == learner.email


@override_settings(AXES_ENABLED=True, ACCOUNT_RATE_LIMITS=False)
def test_axes_alone_locks_out_after_five_failures(client, learner):
    for _ in range(5):
        client.post("/accounts/login/", {"login": learner.email, "password": "wrong-password"})
    r = client.post("/accounts/login/", {"login": learner.email, "password": PASSWORD})
    assert "_auth_user_id" not in client.session
    assert r.status_code == 429


def test_export_holds_only_the_learners_own_data(client, make_learner, course_units):
    a, b = make_learner("a@example.com", "A"), make_learner("b@example.com", "B")
    progress.mark_studied(a, course_units[0].legacy_path)
    progress.mark_studied(b, course_units[1].legacy_path)
    client.force_login(a)
    r = client.get("/me/export")
    assert r["Content-Disposition"].startswith("attachment") and r["Cache-Control"] == "no-store"
    data = json.loads(r.content)
    assert data["account"]["email"] == "a@example.com"
    assert data["profile"]["display_name"] == "A"
    assert [u["page"] for u in data["progress"]["units"]] == [course_units[0].legacy_path]
    assert "b@example.com" not in r.content.decode() and course_units[1].legacy_path not in r.content.decode()
    assert client.get("/me/export").status_code == 200
    client.logout()
    assert client.get("/me/export").status_code == 302


def test_delete_removes_everything_and_anonymises_attempts(client, learner, course_units):
    progress.mark_studied(learner, course_units[0].legacy_path)
    attempt = Attempt.objects.create(user=learner, kind="paper", seed=1)
    client.force_login(learner)
    r = client.post("/me/delete", {"password": "not-it"})
    assert r.status_code == 200 and User.objects.filter(pk=learner.pk).exists()
    r = client.post("/me/delete", {"password": PASSWORD})
    assert r.status_code == 302
    assert not User.objects.filter(pk=learner.pk).exists()
    assert not Profile.objects.exists() and not EmailAddress.objects.exists()
    assert not UnitProgress.objects.exists() and not ActivityEvent.objects.exists()
    attempt.refresh_from_db()
    assert attempt.user is None
    [message] = mail.outbox
    assert message.to == [learner.email] and "deleted" in message.subject
    assert "_auth_user_id" not in client.session


def test_an_account_without_a_password_is_deleted_by_typing_delete(client, learner):
    learner.set_unusable_password()
    learner.save()
    client.force_login(learner)
    assert "Type DELETE" in client.get("/me/delete").content.decode()
    client.post("/me/delete", {"confirm": "delete"})
    assert User.objects.filter(pk=learner.pk).exists()
    client.post("/me/delete", {"confirm": "DELETE"})
    assert not User.objects.filter(pk=learner.pk).exists()


def test_the_admin_needs_a_second_factor_when_required(client, django_user_model):
    from django.apps import apps

    from apps.accounts.apps import AccountsConfig

    staff = django_user_model.objects.create_user("staff@example.com", PASSWORD, is_staff=True, is_superuser=True)
    client.force_login(staff)
    assert client.get("/staff/").status_code == 200
    try:
        with override_settings(ADMIN_OTP_REQUIRED=True):
            AccountsConfig.ready(apps.get_app_config("accounts"))
            r = client.get("/staff/")
            assert r.status_code == 302 and "/staff/login/" in r["Location"]
    finally:
        admin.site.__class__ = AdminSite
    assert client.get("/staff/").status_code == 200


def test_add_totp_device_prints_an_otpauth_uri(django_user_model, capsys):
    django_user_model.objects.create_user("staff@example.com", PASSWORD, is_staff=True)
    call_command("add_totp_device", "staff@example.com")
    assert "otpauth://totp/" in capsys.readouterr().out


def test_the_site_record_is_named(settings):
    site = Site.objects.get(pk=settings.SITE_ID)
    assert site.name == "NRSTATLAB" and site.domain != "example.com"


def test_privacy_page(client):
    body = client.get("/privacy.html").content.decode()
    assert "No adverts" not in body and "no adverts, no trackers" in body.lower().replace("there are ", "")
    for words in ["Download my data", "Delete my account", "failed sign-in", "GitHub Issues"]:
        assert words in body
