from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services


def _exam(slug):
    exam = services.exam_by_slug(slug)
    if exam is None:
        raise Http404("No such exam.")
    return exam


@login_required
def index(request):
    target = services.target_of(request.user)
    rows = [{"exam": e, "s": services.summary(request.user, e), "target": target == e} for e in services.exams()]
    return render(request, "examinations/index.html", {"rows": rows, "target": target})


@login_required
def exam(request, slug):
    exam = _exam(slug)
    return render(request, "examinations/readiness.html", {
        "exam": exam, "r": services.readiness(request.user, exam),
        "is_target": services.target_of(request.user) == exam})


@login_required
@require_POST
def target(request, slug):
    """Make this exam the one the learner is preparing for, or stop. Only ever the
    signed-in learner's own."""
    exam = _exam(slug)
    if request.POST.get("action") == "clear":
        if services.target_of(request.user) == exam:
            services.clear_target(request.user)
    else:
        services.set_target(request.user, exam)
    return redirect("readiness_exam", slug=slug)
