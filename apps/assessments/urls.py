from django.urls import path

from . import views

urlpatterns = [
    path("<int:unit_id>/", views.intro, name="test_intro"),
    path("<int:unit_id>/start", views.start, name="test_start"),
    path("attempt/<uuid:attempt_id>/", views.attempt, name="test_attempt"),
    path("attempt/<uuid:attempt_id>/answer", views.answer, name="test_answer"),
    path("attempt/<uuid:attempt_id>/submit", views.submit, name="test_submit"),
    path("attempt/<uuid:attempt_id>/result", views.result, name="test_result"),
]
