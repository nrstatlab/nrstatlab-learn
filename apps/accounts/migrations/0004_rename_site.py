"""The site is renamed StatsTricks360 (October 2026): rename the Site record that emails quote."""
from django.conf import settings
from django.db import migrations


def rename(apps, schema_editor, name="StatsTricks360"):
    apps.get_model("sites", "Site").objects.filter(pk=settings.SITE_ID).update(name=name)


def unrename(apps, schema_editor):
    rename(apps, schema_editor, name="NRSTATLAB")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_site_record")]
    operations = [migrations.RunPython(rename, unrename)]
