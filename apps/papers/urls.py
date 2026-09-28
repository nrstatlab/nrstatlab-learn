from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="papers_index"),
    path("<slug:slug>/", views.rules, name="paper_rules"),
    path("<slug:slug>/start", views.start, name="paper_start"),
    path("attempt/<uuid:attempt_id>/", views.sitting, name="paper_sitting"),
    path("attempt/<uuid:attempt_id>/answer", views.answer, name="paper_answer"),
    path("attempt/<uuid:attempt_id>/check", views.check, name="paper_check"),
    path("attempt/<uuid:attempt_id>/reveal", views.reveal, name="paper_reveal"),
    path("attempt/<uuid:attempt_id>/submit", views.submit, name="paper_submit"),
    path("attempt/<uuid:attempt_id>/review", views.review, name="paper_review"),
]
