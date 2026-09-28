import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.assessments import services as assessments

from . import services


def _paper(slug):
    paper = services.paper_by_slug(slug)
    if paper is None:
        raise Http404("No such paper.")
    return paper


def _sitting(request, attempt_id):
    """A sitting is only ever its owner's: anyone else gets a 404."""
    s = services.sitting_for(request.user, attempt_id)
    if s is None:
        raise Http404("No such paper sitting.")
    return s


@login_required
def index(request):
    rows = []
    for paper in services.papers():
        last = services.history(request.user, paper)
        rows.append({"paper": paper, "rules": services.rules(paper), "last": last[0] if last else None})
    return render(request, "papers/index.html", {"rows": rows})


@login_required
def rules(request, slug):
    paper = _paper(slug)
    return render(request, "papers/rules.html", {
        "paper": paper, "r": services.rules(paper),
        "open_exam": services.open_sitting(request.user, paper, services.EXAM),
        "open_practice": services.open_sitting(request.user, paper, services.PRACTICE),
        "history": services.history(request.user, paper)})


@login_required
@require_POST
def start(request, slug):
    paper = _paper(slug)
    mode = request.POST.get("mode")
    if mode not in (services.PRACTICE, services.EXAM):
        return redirect("paper_rules", slug=slug)
    s = services.start(request.user, paper, mode)
    return redirect("paper_sitting", attempt_id=s.attempt_id)


@login_required
def sitting(request, attempt_id):
    s = _sitting(request, attempt_id)
    if s.attempt.submitted_at:
        return redirect("paper_review", attempt_id=s.attempt_id)
    questions = services.view(s)
    if s.attempt.mode == services.EXAM:
        return render(request, "papers/exam.html", {
            "s": s, "paper": s.paper, "r": services.rules(s.paper), "questions": questions,
            "answerable": sum(1 for q in questions if not q["withdrawn"]),
            "seconds_left": services.seconds_left(s)})
    if "q" in request.GET and request.GET["q"].isdigit():
        services.move(s, request.GET["q"])
    n = s.position
    q = questions[n - 1]
    revealed = services.reveal(s, n) if n in s.revealed else None
    return render(request, "papers/practice.html", {
        "s": s, "paper": s.paper, "q": q, "n": n, "total": len(questions), "revealed": revealed,
        "study": assessments.unit_links([revealed["uid"]]).get(revealed["uid"]) if revealed else None,
        "answered": sum(1 for x in questions if any(o["chosen"] for o in x.get("options", []))),
        "seen": len(s.revealed)})


def _json(request):
    try:
        data = json.loads(request.body or b"null")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


@login_required
@require_POST
def answer(request, attempt_id):
    s = _sitting(request, attempt_id)
    data = _json(request)
    if data is None:
        return JsonResponse({"error": 'Expected {"question": n, "answer": ...}.'}, status=400)
    try:
        services.answer(s, data.get("question"), data.get("answer"))
    except (services.Late, assessments.AttemptClosed) as e:
        return JsonResponse({"error": str(e)}, status=409)
    except assessments.BadAnswer as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"saved": True})


@login_required
@require_POST
def check(request, attempt_id):
    """Practice mode, a plain form: save the answer given (if any) and show the solution."""
    s = _sitting(request, attempt_id)
    if s.attempt.mode != services.PRACTICE or s.attempt.submitted_at:
        return redirect("paper_sitting", attempt_id=s.attempt_id)
    n = s.position
    raw = request.POST.get(f"q{n}")
    if raw and n not in s.revealed and not request.POST.get("show"):
        try:
            services.answer(s, n, raw)
        except assessments.BadAnswer:
            pass
    services.reveal(s, n)
    return redirect(reverse("paper_sitting", kwargs={"attempt_id": s.attempt_id}) + f"?q={n}#answer")


@login_required
@require_POST
def reveal(request, attempt_id):
    s = _sitting(request, attempt_id)
    data = _json(request) or {}
    try:
        item = services.reveal(s, data.get("question"))
    except assessments.AttemptClosed as e:
        return JsonResponse({"error": str(e)}, status=409)
    except assessments.BadAnswer as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"key": [o["display"] for o in item.get("options", []) if o["key"]],
                         "correct": item["correct"], "answered": item["answered"],
                         "solution_html": item["solution_html"]})


def _form_answers(post, questions):
    out = {}
    for q in questions:
        value = post.get(f"q{q['n']}", "")
        if value and not q["withdrawn"]:
            out[q["n"]] = value
    return out


@login_required
@require_POST
def submit(request, attempt_id):
    s = _sitting(request, attempt_id)
    if not s.attempt.submitted_at:
        # A plain form post carries the answers too. After the time is up it carries
        # nothing that counts: only what was saved in time is scored.
        if request.POST.get("from_form") and not services.late(s):
            for n, raw in _form_answers(request.POST, services.view(s)).items():
                try:
                    services.answer(s, n, raw)
                except (assessments.BadAnswer, services.Late):
                    pass
        services.submit(s)
    return redirect("paper_review", attempt_id=s.attempt_id)


@login_required
def review(request, attempt_id):
    s = _sitting(request, attempt_id)
    if not s.attempt.submitted_at:
        return redirect("paper_sitting", attempt_id=s.attempt_id)
    return render(request, "papers/review.html", {"s": s, "paper": s.paper, "r": services.review(s)})
