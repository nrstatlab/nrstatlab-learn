import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.study import services as study

from . import engine
from .models import Attempt, UnitTest


def _unit_test(unit_id):
    ut = UnitTest.objects.select_related("unit").filter(unit_id=unit_id).first()
    if ut is None:
        raise Http404("No test for this unit.")
    return ut


def _own_attempt(request, attempt_id):
    """An attempt id is only ever its owner's: anyone else gets a 404."""
    attempt = Attempt.objects.select_related("unit_test__unit").filter(pk=attempt_id, kind=Attempt.UNIT_TEST).first()
    if attempt is None or attempt.user_id != request.user.pk:
        raise Http404("No such test.")
    return attempt


@login_required
def intro(request, unit_id):
    ut = _unit_test(unit_id)
    open_attempt = Attempt.objects.filter(user=request.user, unit_test=ut, submitted_at__isnull=True).first()
    if open_attempt:
        return redirect("test_attempt", attempt_id=open_attempt.pk)
    try:
        engine.check_open(request.user, ut)
        locked = ""
    except engine.TestLocked as e:
        locked = str(e)
    return render(request, "assessments/intro.html", {
        "ut": ut, "unit": ut.unit, "locked": locked, "history": engine.history(request.user, ut),
        "percent": engine.percent})


@login_required
@require_POST
def start(request, unit_id):
    ut = _unit_test(unit_id)
    try:
        attempt = engine.start(request.user, ut)
    except engine.TestLocked:
        return redirect("test_intro", unit_id=unit_id)
    return redirect("test_attempt", attempt_id=attempt.pk)


@login_required
def attempt(request, attempt_id):
    a = _own_attempt(request, attempt_id)
    if a.submitted_at:
        return redirect("test_result", attempt_id=a.pk)
    return render(request, "assessments/attempt.html", {
        "attempt": a, "ut": a.unit_test, "unit": a.unit_test.unit, "questions": engine.public_view(a)})


@login_required
@require_POST
def answer(request, attempt_id):
    a = _own_attempt(request, attempt_id)
    try:
        data = json.loads(request.body or b"null")
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        return JsonResponse({"error": 'Expected {"question": n, "answer": ...}.'}, status=400)
    try:
        engine.save_answer(a, data.get("question"), data.get("answer"))
    except engine.AttemptClosed as e:
        return JsonResponse({"error": str(e)}, status=409)
    except engine.BadAnswer as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"saved": True})


def _form_answers(post, questions):
    """The answers in a plain form post (the page works without JavaScript)."""
    out = {}
    for q in questions:
        n = q["n"]
        if q["qtype"] == "multiple":
            out[n] = post.getlist(f"q{n}")
        elif q["qtype"] == "match":
            out[n] = {row["label"]: post.get(f"q{n}-{row['label']}", "") for row in q["left"]}
        else:
            out[n] = post.get(f"q{n}", "")
    return out


@login_required
@require_POST
def submit(request, attempt_id):
    a = _own_attempt(request, attempt_id)
    if not a.submitted_at:
        if request.POST.get("from_form"):
            # The form adds what it carries; it never clears an answer saved earlier
            # (an unanswered radio group is simply absent from a form post).
            for n, raw in _form_answers(request.POST, engine.public_view(a)).items():
                if raw in ("", [], None) or (isinstance(raw, dict) and not any(raw.values())):
                    continue
                try:
                    engine.save_answer(a, n, raw)
                except engine.BadAnswer:
                    pass
        engine.submit(a)
    return redirect("test_result", attempt_id=a.pk)


@login_required
def result(request, attempt_id):
    a = _own_attempt(request, attempt_id)
    if not a.submitted_at:
        return redirect("test_attempt", attempt_id=a.pk)
    return render(request, "assessments/result.html", {
        "attempt": a, "ut": a.unit_test, "unit": a.unit_test.unit, "r": engine.result_view(a),
        "course_home": study.course_home(a.unit_test.unit.legacy_path)})
