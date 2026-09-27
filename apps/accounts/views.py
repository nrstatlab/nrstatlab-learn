import json

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from axes.models import AccessAttempt
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import services
from .forms import DeleteAccountForm


def _iso(dt):
    return dt.isoformat() if dt else None


def export_data(user):
    """Everything the application keeps about this learner, as plain data."""
    profile = services.profile_for(user)
    data = {
        "exported_at": _iso(timezone.now()),
        "account": {"email": user.email, "joined": _iso(user.date_joined), "last_login": _iso(user.last_login),
                    "has_password": user.has_usable_password()},
        "profile": {"display_name": profile.display_name, "age_confirmed": profile.age_confirmed,
                    "terms_accepted_at": _iso(profile.terms_accepted_at),
                    "browser_import_done": profile.browser_import_done},
        "email_addresses": [{"email": e.email, "verified": e.verified, "primary": e.primary}
                            for e in EmailAddress.objects.filter(user=user).order_by("email")],
        "sign_in_with": [{"provider": s.provider, "linked": _iso(s.date_joined)}
                         for s in SocialAccount.objects.filter(user=user).order_by("provider")],
    }
    for name, fn in sorted(services.exporters().items()):
        data[name] = fn(user)
    return data


@login_required
def export(request):
    body = json.dumps(export_data(request.user), indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="nrstatlab-my-data.json"'
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def delete(request):
    user = request.user
    form = DeleteAccountForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        email = user.email
        send_mail(
            "NRSTATLAB: your account has been deleted",
            "Your NRSTATLAB account and everything kept with it (your progress, your profile and your "
            "sign-in details) have been deleted.\n\nThe study material is still free to read without an "
            "account. If you did not ask for this, reply through the site's GitHub Issues page.\n",
            None, [email])
        logout(request)
        AccessAttempt.objects.filter(username=email.lower()).delete()
        user.delete()  # cascades to profile, progress, events, email addresses; attempts are anonymised
        return redirect("/?account=deleted")
    return render(request, "accounts/delete.html", {"form": form})
