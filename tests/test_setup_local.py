"""setup_local prepares a computer for the offline check (docs/LOCAL-CHECK.md)."""
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.assessments.models import Attempt
from apps.core.management.commands import setup_local
from apps.progress import services as progress
from apps.progress.models import UnitProgress

pytestmark = pytest.mark.django_db


def test_it_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("setup_local", "--skip-import")


def test_it_makes_the_three_accounts_once(settings, django_user_model, capsys):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    emails = {setup_local.OWNER[0], setup_local.NEW[0], setup_local.PROGRESSED[0], setup_local.REVIEWER[0]}
    assert set(django_user_model.objects.filter(email__in=emails).values_list("email", flat=True)) == emails
    assert django_user_model.objects.get(email=setup_local.OWNER[0]).is_staff
    call_command("setup_local", "--skip-import")
    assert "already there" in capsys.readouterr().out
    assert django_user_model.objects.filter(email__in=emails).count() == 4


def test_the_learner_with_progress_has_a_pass_and_a_fail(settings, django_user_model):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    user = django_user_model.objects.get(email=setup_local.PROGRESSED[0])
    statuses = dict(UnitProgress.objects.filter(user=user).values_list("unit__legacy_path", "status"))
    assert statuses == {setup_local.STUDIED[0]: "studied", setup_local.STUDIED[1]: "passed"}
    scores = sorted(Attempt.objects.filter(user=user).exclude(kind=Attempt.PAPER).values_list("score", flat=True))
    assert scores == [3, 10]


def test_the_learner_with_progress_has_sat_a_paper(settings, django_user_model):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    user = django_user_model.objects.get(email=setup_local.PROGRESSED[0])
    sat = Attempt.objects.get(user=user, kind=Attempt.PAPER)
    # 90 right, 30 wrong at -0.33, of the 149 questions that count (docs/LOCAL-CHECK.md, 4.8)
    assert (sat.mode, sat.score, sat.max_score) == ("exam", Decimal("80.10"), Decimal("149.00"))
    assert [p["score"] for p in progress.recent_papers(user)] == ["80.10"]
    assert user.exam_target.exam.slug == "ugc-net"          # the dashboard's "Your exam" card


def test_the_demo_learners_can_sign_in(settings, client):
    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    for email in (setup_local.NEW[0], setup_local.PROGRESSED[0], setup_local.OWNER[0], setup_local.REVIEWER[0]):
        client.post("/accounts/login/", {"login": email, "password": setup_local.PASSWORD})
        assert "_auth_user_id" in client.session, email
        client.logout()


def test_the_review_demo_data(settings, django_user_model):
    """Two reviewers, a draft by the owner that only the other may approve, and 40
    anonymous sittings in which one question is planted with a negative r_pb."""
    from apps.assessments import review, stats
    from apps.assessments.models import Question

    settings.DEBUG = True
    call_command("setup_local", "--skip-import")
    owner = django_user_model.objects.get(email=setup_local.OWNER[0])
    second = django_user_model.objects.get(email=setup_local.REVIEWER[0])
    assert review.is_reviewer(owner) and review.is_reviewer(second) and not second.is_superuser
    draft = Question.objects.get(uid="local-demo-draft-001")
    with pytest.raises(review.ReviewRefused):
        review.approve(draft, owner)
    review.approve(draft, second)
    flagged = [uid for uid, _ in stats.run(notify=False)["flagged"]]
    assert flagged == ["ugc-mcq-u01-q10"]
