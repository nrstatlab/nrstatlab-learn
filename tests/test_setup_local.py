"""setup_local prepares a computer for the offline check (docs/LOCAL-CHECK.md)."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.assessments.models import Attempt
from apps.core.management.commands import setup_local
from apps.progress.models import UnitProgress

pytestmark = pytest.mark.django_db


def test_it_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("setup_local", "--skip-import")


def test_it_makes_the_three_accounts_once(settings, django_user_model, capsys):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    emails = {setup_local.OWNER[0], setup_local.NEW[0], setup_local.PROGRESSED[0]}
    assert set(django_user_model.objects.filter(email__in=emails).values_list("email", flat=True)) == emails
    assert django_user_model.objects.get(email=setup_local.OWNER[0]).is_staff
    call_command("setup_local", "--skip-import")
    assert "already there" in capsys.readouterr().out
    assert django_user_model.objects.filter(email__in=emails).count() == 3


def test_the_learner_with_progress_has_a_pass_and_a_fail(settings, django_user_model):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    user = django_user_model.objects.get(email=setup_local.PROGRESSED[0])
    statuses = dict(UnitProgress.objects.filter(user=user).values_list("unit__legacy_path", "status"))
    assert statuses == {setup_local.STUDIED[0]: "studied", setup_local.STUDIED[1]: "passed"}
    scores = sorted(Attempt.objects.filter(user=user).values_list("score", flat=True))
    assert scores == [3, 10]


def test_the_demo_learners_can_sign_in(settings, client):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    for email in (setup_local.NEW[0], setup_local.PROGRESSED[0], setup_local.OWNER[0]):
        client.post("/accounts/login/", {"login": email, "password": setup_local.PASSWORD})
        assert "_auth_user_id" in client.session, email
        client.logout()
