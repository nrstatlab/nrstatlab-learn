import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounts import services as accounts

from . import services


def json_login_required(view):
    """For the endpoints learn.js calls: a 403 in JSON, not a redirect to a login page."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sign in to save progress."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def _body(request):
    try:
        data = json.loads(request.body or b"null")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


@require_POST
@json_login_required
def studied(request):
    data = _body(request)
    if data is None or not isinstance(data.get("page"), str) or not isinstance(data.get("done", True), bool):
        return JsonResponse({"error": 'Expected {"page": "<page id>", "done": true|false}.'}, status=400)
    try:
        status = services.mark_studied(request.user, data["page"], data.get("done", True))
    except services.NotAUnit:
        return JsonResponse({"error": "That page is not a unit that can be marked."}, status=404)
    return JsonResponse({"page": data["page"], "status": status, "done": status in services.DONE})


@require_POST
@json_login_required
def import_browser(request):
    data = _body(request)
    try:
        result = services.import_browser(request.user, (data or {}).get("done"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse(result)


@require_POST
@json_login_required
def dismiss_import(request):
    services.dismiss_import(request.user)
    return JsonResponse({"ok": True})


@login_required
def dashboard(request):
    user = request.user
    last, nxt = services.last_studied(user)
    return render(request, "progress/dashboard.html", {
        "display_name": accounts.display_name(user),
        "last": last,
        "next": nxt,
        "courses": services.course_summaries(user),
        "streak": services.streak(user),
    })
