"""Name the Site record, so emails say NRSTATLAB and the real host, not example.com."""
from urllib.parse import urlsplit

from django.conf import settings
from django.db import migrations


def name_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    domain = urlsplit(settings.SITE_ORIGIN).netloc or "localhost"
    Site.objects.update_or_create(pk=settings.SITE_ID, defaults={"domain": domain, "name": "NRSTATLAB"})


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_browser_import_done"),
        ("sites", "0002_alter_domain_unique"),
    ]
    operations = [migrations.RunPython(name_site, migrations.RunPython.noop)]
