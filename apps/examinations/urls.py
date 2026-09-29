from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="readiness_index"),
    path("<slug:slug>/", views.exam, name="readiness_exam"),
    path("<slug:slug>/target", views.target, name="readiness_target"),
]
