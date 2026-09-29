"""URL map: ARCHITECTURE.md §5. Application routes never end in .html, so they cannot
collide with a page of the site, except /privacy.html, which the site does not have
(tests/test_pages.py checks it). Every other path is a page of the site (core.views.page)."""
from django.contrib import admin
from django.urls import include, path, re_path

from apps.core import views as core

urlpatterns = [
    path("staff/", admin.site.urls),
    path("healthz", core.health),
    path("accounts/", include("allauth.urls")),
    path("me/", include("apps.accounts.urls")),
    path("me/", include("apps.progress.urls")),
    path("test/", include("apps.assessments.urls")),
    path("papers/", include("apps.papers.urls")),
    path("readiness/", include("apps.examinations.urls")),
    path("privacy.html", core.privacy, name="privacy"),
    re_path(r"^(?P<path>.*)$", core.page),
]

handler404 = "apps.core.views.not_found"
