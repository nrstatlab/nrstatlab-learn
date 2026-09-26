import pytest
from django.conf import settings
from django.core.management import call_command

from apps.core.importer import Source


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Import the whole site once into the test database; every test sees it."""
    with django_db_blocker.unblock():
        call_command("import_site", verbosity=0)


@pytest.fixture(scope="session")
def source():
    return Source.read(settings.CONTENT_DIR)
