from django import forms
from django.utils import timezone
from django.utils.safestring import mark_safe

from .models import Profile


class SignupForm(forms.Form):
    """The fields allauth adds to sign-up, by email and by Google alike.

    Sign-up is for learners aged 18 and over at launch (ARCHITECTURE.md §1, decision 4).
    Nothing else is asked: the display name is the only personal detail besides the email.
    """

    display_name = forms.CharField(
        max_length=60, label="Your name, as the dashboard should greet you",
        widget=forms.TextInput(attrs={"autocomplete": "nickname"}))
    age_confirmed = forms.BooleanField(required=True, label="I am 18 or over")
    privacy_read = forms.BooleanField(
        required=True, label=mark_safe('I have read the <a href="/privacy.html" target="_blank">privacy notice</a>'))

    field_order = ["display_name", "email", "password1", "password2", "age_confirmed", "privacy_read"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""

    def clean_display_name(self):
        name = " ".join(self.cleaned_data["display_name"].split())
        if not name:
            raise forms.ValidationError("Please give a name.")
        return name

    def signup(self, request, user):
        Profile.objects.update_or_create(user=user, defaults={
            "display_name": self.cleaned_data["display_name"],
            "age_confirmed": True,
            "terms_accepted_at": timezone.now(),
        })


class DeleteAccountForm(forms.Form):
    """Asks for the password; an account with no password (Google only) types DELETE."""

    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    confirm = forms.CharField(required=False, label='Type DELETE to confirm')

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user.has_usable_password():
            del self.fields["confirm"]
            self.fields["password"].required = True
            self.fields["password"].label = "Your password"
        else:
            del self.fields["password"]
            self.fields["confirm"].required = True

    def clean(self):
        data = super().clean()
        if "password" in self.fields and data.get("password") and not self.user.check_password(data["password"]):
            raise forms.ValidationError("That password is not right.")
        if "confirm" in self.fields and data.get("confirm") is not None and data.get("confirm").strip() != "DELETE":
            raise forms.ValidationError("Type DELETE, in capitals, to confirm.")
        return data
