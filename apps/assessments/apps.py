from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.assessments"

    def ready(self):
        from apps.accounts import services as accounts

        from . import services

        accounts.register_exporter("tests", services.export)
