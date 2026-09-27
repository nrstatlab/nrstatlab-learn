from django.db import connection
from django.http import HttpResponse, HttpResponseNotFound, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render

from apps.study import services as study

from .inject import inject
from .models import Redirect

HTML = "text/html; charset=utf-8"


def _redirect_to(new_path):
    return HttpResponsePermanentRedirect(new_path if new_path.startswith("http") else "/" + new_path)


def page(request, path=""):
    """Every address of the static site, served at the same path (BUILD-GUIDE Step 6).

    Order: a redirect stub; a page; a folder (served as its index.html, as GitHub Pages
    does, with /folder redirected to /folder/); otherwise the site's own 404 page.
    """
    legacy = path.lstrip("/")
    if legacy == "" or legacy.endswith("/"):
        legacy += "index.html"
    elif not legacy.endswith(".html") and (study.exists(legacy + "/index.html")
                                           or Redirect.objects.filter(old_path=legacy + "/index.html").exists()):
        return HttpResponsePermanentRedirect("/" + path.lstrip("/") + "/")

    redirect = Redirect.objects.filter(old_path=legacy).first()
    if redirect:
        return _redirect_to(redirect.new_path)
    found = study.find(legacy)
    if found is None:
        return not_found(request)
    return HttpResponse(inject(study.render_html(found), request, found.legacy_path), content_type=HTML)


def not_found(request, exception=None):
    stored = study.find("404.html")
    body = inject(study.render_html(stored), request) if stored else "<h1>Page not found</h1>"
    return HttpResponseNotFound(body, content_type=HTML)


def privacy(request):
    return render(request, "core/privacy.html")


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok", "database": "ok"})
