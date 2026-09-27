import pytest
from django.conf import settings
from django.core.management import call_command

from apps.core.importer import Source


def pytest_collection_modifyitems(items):
    """Browser tests run on a live server, which needs a real transaction and so
    empties the database after each one. They run last, and import the site again
    themselves (tests/test_browser.py)."""
    items.sort(key=lambda item: item.get_closest_marker("browser") is not None)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Import the whole site once into the test database; every test sees it."""
    with django_db_blocker.unblock():
        call_command("import_site", verbosity=0)


@pytest.fixture(scope="session")
def source():
    return Source.read(settings.CONTENT_DIR)


PASSWORD = "a-long-password-1"


@pytest.fixture
def make_learner(django_user_model):
    """A learner who signed up and verified their email."""
    from allauth.account.models import EmailAddress

    from apps.accounts.models import Profile

    def make(email="learner@example.com", name="Asha", password=PASSWORD):
        user = django_user_model.objects.create_user(email, password)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        Profile.objects.create(user=user, display_name=name, age_confirmed=True)
        return user
    return make


@pytest.fixture
def learner(make_learner):
    return make_learner()


@pytest.fixture
def course_units():
    """The units of one course, in order."""
    from apps.study.models import Course
    course = Course.objects.get(path="statistics/sampling-theory")
    return list(course.units.order_by("order"))
