from django.apps import AppConfig


class ExaminationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.examinations"

    def ready(self):
        from apps.accounts import services as accounts
        from apps.progress import services as progress

        from . import services

        accounts.register_exporter("exam_target", services.export_target)
        progress.register_card(services.dashboard_card)
