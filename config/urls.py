"""URL map: ARCHITECTURE.md §5. Application routes never end in .html, so they cannot
collide with a page of the site; every other path is a page of the site (core.views.page)."""
from django.contrib import admin
from django.urls import path, re_path

from apps.core import views as core

urlpatterns = [
    path("staff/", admin.site.urls),
    path("healthz", core.health),
    re_path(r"^(?P<path>.*)$", core.page),
]

handler404 = "apps.core.views.not_found"
