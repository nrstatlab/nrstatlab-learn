from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("progress/studied", views.studied, name="progress_studied"),
    path("progress/import", views.import_browser, name="progress_import"),
    path("progress/import/dismiss", views.dismiss_import, name="progress_import_dismiss"),
]
