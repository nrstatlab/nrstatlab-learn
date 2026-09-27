from django.urls import path

from . import views

urlpatterns = [
    path("export", views.export, name="account_export"),
    path("delete", views.delete, name="account_delete"),
]
