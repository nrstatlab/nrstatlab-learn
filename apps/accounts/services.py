"""The accounts app's interface (ARCHITECTURE.md §3). Every app may use it; accounts
itself uses no other app. Apps add their part of a learner's data export here, from
their AppConfig.ready(), so accounts never needs to know them."""
from django.utils.crypto import salted_hmac

from .models import Profile

_EXPORTERS = {}


def register_exporter(name, fn):
    """fn(user) -> JSON-serialisable data, included in /me/export under `name`."""
    _EXPORTERS[name] = fn


def exporters():
    return dict(_EXPORTERS)


def profile_for(user):
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"display_name": ""})
    return profile


def display_name(user):
    return profile_for(user).display_name or user.email.split("@")[0]


def account_marker(user):
    """An opaque id for this account, for the browser to tell accounts apart.
    It is not the email and cannot be turned back into it."""
    return salted_hmac("nrstat-account-marker", str(user.pk)).hexdigest()[:20]


def import_offer_open(user):
    return not profile_for(user).browser_import_done


def mark_import_done(user):
    Profile.objects.filter(pk=profile_for(user).pk).update(browser_import_done=True)


def create_verified_account(email, password, display_name, staff=False, superuser=None):
    """An account whose email is already verified, for local demonstration data
    (setup_local). Real accounts are made by signing up."""
    from allauth.account.models import EmailAddress
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(email, password, is_staff=staff,
                                                 is_superuser=staff if superuser is None else superuser)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    Profile.objects.create(user=user, display_name=display_name, age_confirmed=True)
    return user
