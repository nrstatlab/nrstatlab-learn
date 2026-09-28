"""The unit test engine (BUILD-GUIDE Step 10). Reached through assessments.services.

- A test opens when the learner has studied (or passed) the unit and the unit has
  at least UnitTest.n_questions published questions.
- Questions are drawn unseen first, balanced across difficulty bands, and the
  question order and each question's options are shuffled from the attempt's seed,
  so a reload shows the same test.
- Nothing that gives an answer away reaches the page before submission: options
  are identified by tokens made for this attempt, never by their labels, whose
  order is the source's (and the UGC NET key is "A" more often than not).
- Scoring is on the server. A question that is no longer published when the test
  is submitted (flagged after the draw, say) counts neither for nor against.
"""
import hmac
import json
import random
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.progress import services as progress
from apps.study import services as study

from .models import Attempt, Choice, Question, Response, UnitTest

OPEN_STATUSES = ("studied", "passed")
BANDS = ("easy", "medium", "hard", "unrated")


class TestLocked(Exception):
    pass


class AttemptClosed(Exception):
    pass


class BadAnswer(Exception):
    pass


# ---------------------------------------------------------------- availability

def pool(unit_test):
    return list(Question.objects.filter(unit_links__unit=unit_test.unit, status=Question.PUBLISHED)
                .select_related("stats").distinct().order_by("uid"))


def test_for_unit(unit):
    """The unit's test when it has enough published questions, else None."""
    ut = UnitTest.objects.filter(unit=unit).first()
    if ut is None:
        return None
    n = Question.objects.filter(unit_links__unit=unit, status=Question.PUBLISHED).distinct().count()
    return ut if n >= ut.n_questions else None


def availability(user, page_id):
    """What a unit page says about its test: {"has_test": False} or
    {"has_test", "url", "n", "pass_mark", "open", "best", "passed"}."""
    unit = study.unit_by_path(page_id)
    ut = test_for_unit(unit) if unit else None
    if ut is None:
        return {"has_test": False}
    out = {"has_test": True, "url": f"/test/{unit.pk}/", "n": ut.n_questions, "pass_mark": ut.pass_mark}
    if user.is_authenticated:
        status = progress.status_of(user, page_id)
        best = (Attempt.objects.filter(user=user, unit_test=ut, submitted_at__isnull=False)
                .order_by("-score").values_list("score", "max_score").first())
        out.update(open=status in OPEN_STATUSES, passed=status == "passed",
                   best=float(percent(*best)) if best else None,
                   resume=Attempt.objects.filter(user=user, unit_test=ut, submitted_at__isnull=True).exists())
    return out


def check_open(user, ut):
    if progress.status_of(user, ut.unit.legacy_path) not in OPEN_STATUSES:
        raise TestLocked("Mark the unit done first: its test opens once you have studied it.")
    if test_for_unit(ut.unit) is None:
        raise TestLocked("This unit does not have enough checked questions for a test yet.")


# ---------------------------------------------------------------- drawing

def band(q):
    stats = getattr(q, "stats", None)
    if stats is not None and stats.n >= 30 and stats.difficulty is not None:
        return "easy" if stats.difficulty >= 0.7 else "hard" if stats.difficulty < 0.4 else "medium"
    if q.difficulty:
        return "easy" if q.difficulty <= 2 else "medium" if q.difficulty == 3 else "hard"
    return "unrated"


def seen_uids(user, ut):
    seen = set()
    for uids in Attempt.objects.filter(user=user, unit_test=ut).values_list("question_uids", flat=True):
        seen.update(uids)
    return seen


def draw(ut, user, seed):
    """n question uids: unseen first, then the rest; within each, round-robin across
    difficulty bands; then shuffled."""
    rng = random.Random(seed)
    questions = pool(ut)
    seen = seen_uids(user, ut)
    picked = []
    for fresh in (True, False):
        groups = {b: [] for b in BANDS}
        for q in questions:
            if (q.uid not in seen) == fresh and q.uid not in picked:
                groups[band(q)].append(q.uid)
        for g in groups.values():
            rng.shuffle(g)
        while len(picked) < ut.n_questions and any(groups.values()):
            for b in BANDS:
                if groups[b] and len(picked) < ut.n_questions:
                    picked.append(groups[b].pop())
    rng.shuffle(picked)
    return picked


@transaction.atomic
def start(user, ut):
    """The learner's open attempt at this test, or a new one."""
    check_open(user, ut)
    open_ = Attempt.objects.filter(user=user, unit_test=ut, submitted_at__isnull=True).first()
    if open_:
        return open_
    seed = secrets.randbits(62)
    try:
        with transaction.atomic():
            return Attempt.objects.create(user=user, kind=Attempt.UNIT_TEST, unit_test=ut, mode="unit",
                                          seed=seed, question_uids=draw(ut, user, seed))
    except IntegrityError:  # a second tab started one at the same moment
        return Attempt.objects.get(user=user, unit_test=ut, submitted_at__isnull=True)


# ---------------------------------------------------------------- what the page may show

def token(attempt, uid, side, label):
    msg = f"{attempt.pk}|{uid}|{side}|{label}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, "sha256").hexdigest()[:16]


def _questions(attempt):
    by_uid = {q.uid: q for q in Question.objects.filter(uid__in=attempt.question_uids).prefetch_related("choices")}
    return [by_uid[u] for u in attempt.question_uids if u in by_uid]


def _order(attempt, q, choices):
    """Unit tests shuffle each question's options from the attempt's seed. An old paper
    keeps the order it was printed in, as the candidates saw it."""
    choices = list(choices)
    if attempt.kind == Attempt.PAPER:
        return choices
    random.Random(f"{attempt.seed}:{q.uid}").shuffle(choices)
    return choices


def _display(attempt, c, k):
    """An option's letter on the page: A, B, C… in a unit test; on an old paper, the
    label the paper printed (1–4 on the APPSC papers)."""
    return c.label if attempt.kind == Attempt.PAPER else "ABCDEFGH"[k]


def public_view(attempt):
    """The attempt as the test page shows it: stems and option texts, options named by
    tokens, and the learner's saved answers. No key, no solution, no is_correct."""
    saved = {r.question.uid: r.answer for r in attempt.responses.select_related("question")}
    out = []
    for i, q in enumerate(_questions(attempt), 1):
        item = {"n": i, "qtype": q.qtype, "stem_html": q.stem_html}
        answer = saved.get(q.uid) or {}
        if q.qtype == Question.MATCH:
            left = [c for c in q.choices.all() if c.side == Choice.LEFT]
            right = _order(attempt, q, [c for c in q.choices.all() if c.side == Choice.RIGHT])
            pairs = answer.get("pairs", {})
            item["left"] = [{"label": c.label, "text_html": c.text_html,
                             "chosen": token(attempt, q.uid, "right", pairs[c.label]) if c.label in pairs else ""}
                            for c in left]
            item["right"] = [{"token": token(attempt, q.uid, "right", c.label), "text_html": c.text_html,
                              "display": _roman(k)} for k, c in enumerate(right, 1)]
        elif q.qtype == Question.NUMERIC:
            item["value"] = answer.get("value", "")
        else:
            chosen = set(answer.get("choices", [])) | ({answer["choice"]} if answer.get("choice") else set())
            item["options"] = [{"token": token(attempt, q.uid, "option", c.label), "text_html": c.text_html,
                                "display": _display(attempt, c, k), "chosen": c.label in chosen}
                               for k, c in enumerate(_order(attempt, q, [c for c in q.choices.all() if not c.side]))]
        out.append(item)
    return out


def _roman(k):
    return ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"][k - 1]


# ---------------------------------------------------------------- answering

def _label_for(attempt, q, side, tok):
    for c in q.choices.all():
        if (c.side == Choice.RIGHT if side == "right" else not c.side) and hmac.compare_digest(
                token(attempt, q.uid, side, c.label), str(tok)):
            return c.label
    raise BadAnswer("That option is not part of this question.")


def normalise(attempt, q, raw):
    """A submitted answer (tokens, or a number) as stored: labels, never tokens."""
    if raw in (None, "", [], {}):
        return None
    if q.qtype in (Question.SINGLE, Question.ASSERTION):
        return {"choice": _label_for(attempt, q, "option", raw)}
    if q.qtype == Question.MULTIPLE:
        raw = raw if isinstance(raw, list) else [raw]
        return {"choices": sorted({_label_for(attempt, q, "option", t) for t in raw})}
    if q.qtype == Question.NUMERIC:
        value = str(raw).strip().replace(",", "")
        try:
            Decimal(value)
        except InvalidOperation as e:
            raise BadAnswer("Enter a number, such as 0.58 or -3.") from e
        return {"value": value}
    if q.qtype == Question.MATCH:
        if not isinstance(raw, dict):
            raise BadAnswer("Expected a pairing for each item.")
        left = {c.label for c in q.choices.all() if c.side == Choice.LEFT}
        return {"pairs": {k: _label_for(attempt, q, "right", v) for k, v in raw.items() if k in left and v}}
    raise BadAnswer("Unknown question type.")


def _question_at(attempt, n):
    try:
        uid = attempt.question_uids[int(n) - 1]
    except (ValueError, IndexError, TypeError) as e:
        raise BadAnswer("No such question in this test.") from e
    return Question.objects.prefetch_related("choices").get(uid=uid)


@transaction.atomic
def save_answer(attempt, n, raw):
    attempt = Attempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.submitted_at:
        raise AttemptClosed("This test has been submitted; its answers can no longer change.")
    q = _question_at(attempt, n)
    answer = normalise(attempt, q, raw)
    if answer is None:
        Response.objects.filter(attempt=attempt, question=q).delete()
    else:
        Response.objects.update_or_create(attempt=attempt, question=q, defaults={"answer": answer})
    return answer


# ---------------------------------------------------------------- scoring

def is_correct(q, answer):
    if not answer:
        return False
    if q.qtype in (Question.SINGLE, Question.ASSERTION):
        return answer.get("choice") in {c.label for c in q.choices.all() if c.is_correct and not c.side}
    if q.qtype == Question.MULTIPLE:
        return set(answer.get("choices", [])) == {c.label for c in q.choices.all() if c.is_correct and not c.side}
    if q.qtype == Question.NUMERIC:
        try:
            return abs(Decimal(answer["value"]) - Decimal(q.answer_text)) <= (q.tolerance or Decimal(0))
        except (KeyError, InvalidOperation):
            return False
    if q.qtype == Question.MATCH:
        return answer.get("pairs", {}) == json.loads(q.answer_text)
    return False


def percent(score, max_score):
    if not max_score:
        return Decimal(0)
    return (Decimal(score) * 100 / Decimal(max_score)).quantize(Decimal("0.01"))


def grade(attempt):
    """Mark every response, and say for each question (in order) whether it counts,
    was answered and is right. A question that is not published when this runs
    (flagged, or retired) does not count: its response is marked neither right nor
    wrong. Shared by unit tests and old papers, so doubt is treated alike."""
    responses = {r.question_id: r for r in attempt.responses.all()}
    out = []
    for n, q in enumerate(_questions(attempt), 1):
        r = responses.get(q.pk)
        counts = q.status == Question.PUBLISHED
        ok = counts and is_correct(q, r.answer if r else None)
        if r:
            r.correct = ok if counts else None
            r.save(update_fields=["correct"])
        out.append({"n": n, "uid": q.uid, "counts": counts, "answered": r is not None, "correct": ok})
    return out


def close(attempt, score, max_score):
    """Freeze a scored attempt."""
    attempt.score, attempt.max_score, attempt.submitted_at = score, max_score, timezone.now()
    attempt.save(update_fields=["score", "max_score", "submitted_at"])
    return attempt


@transaction.atomic
def submit(attempt):
    """Score and freeze a unit test. Returns the attempt. A pass marks the unit passed."""
    attempt = Attempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.submitted_at:
        return attempt
    marks = grade(attempt)
    score = sum(1 for m in marks if m["counts"] and m["correct"])
    max_score = sum(1 for m in marks if m["counts"])
    close(attempt, score, max_score)
    ut = attempt.unit_test
    pct = percent(score, max_score)
    progress.record_test(attempt.user, ut.unit.legacy_path, score=pct, passed=bool(max_score) and pct >= ut.pass_mark,
                         attempt_id=attempt.pk)
    return attempt


def review_items(attempt, only=None):
    """Every question with the learner's answer, the key and the working: for a
    submitted attempt, or (only=n) one question of a practice attempt, through reveal()."""
    responses = {r.question_id: r for r in attempt.responses.all()}
    items = []
    for i, q in enumerate(_questions(attempt), 1):
        if only is not None and i != only:
            continue
        r = responses.get(q.pk)
        answer = r.answer if r else None
        correct = bool(r and r.correct) if attempt.submitted_at else is_correct(q, answer)
        item = {"n": i, "uid": q.uid, "qtype": q.qtype, "stem_html": q.stem_html, "solution_html": q.solution_html,
                "voided": q.status != Question.PUBLISHED, "flag_reason": q.flag_reason,
                "correct": correct, "answered": bool(answer)}
        if q.qtype == Question.MATCH:
            key = json.loads(q.answer_text)
            texts = {c.label: c.text_html for c in q.choices.all()}
            item["rows"] = [{"left": texts[c.label], "yours": texts.get((answer or {}).get("pairs", {}).get(c.label), ""),
                             "key": texts[key[c.label]]} for c in q.choices.all() if c.side == Choice.LEFT]
        elif q.qtype == Question.NUMERIC:
            item.update(yours=(answer or {}).get("value", ""), key=q.answer_text,
                        tolerance=q.tolerance)
        else:
            chosen = set((answer or {}).get("choices", [])) | ({answer["choice"]} if answer and answer.get("choice") else set())
            item["options"] = [{"text_html": c.text_html, "display": _display(attempt, c, k), "chosen": c.label in chosen,
                                "key": c.is_correct}
                               for k, c in enumerate(_order(attempt, q, [c for c in q.choices.all() if not c.side]))]
        items.append(item)
    return items


def result_view(attempt):
    """After a unit test: every question, and the unit to go back to."""
    if not attempt.submitted_at:
        raise AttemptClosed("Not submitted yet.")
    items = review_items(attempt)
    ut = attempt.unit_test
    pct = percent(attempt.score, attempt.max_score)
    return {"items": items, "score": attempt.score, "max_score": attempt.max_score, "percent": pct,
            "passed": bool(attempt.max_score) and pct >= ut.pass_mark, "pass_mark": ut.pass_mark,
            "unit_title": ut.unit.title, "unit_path": ut.unit.legacy_path,
            "voided": sum(1 for i in items if i["voided"])}


# ---------------------------------------------------------------- old papers (papers.services)

def start_paper(user, uids, mode):
    """A new attempt at an old paper: its questions in the paper's order."""
    return Attempt.objects.create(user=user, kind=Attempt.PAPER, mode=mode, seed=0, question_uids=list(uids))


def reveal(attempt, n):
    """Practice mode: one question's key and working, on the learner's asking. Never
    for an exam attempt, whose keys wait for the review."""
    if attempt.kind != Attempt.PAPER or attempt.mode != "practice":
        raise AttemptClosed("Solutions are shown after an exam is submitted, not during it.")
    try:
        n = int(n)
    except (TypeError, ValueError) as e:
        raise BadAnswer("No such question.") from e
    items = review_items(attempt, only=n)
    if not items:
        raise BadAnswer("No such question.")
    return items[0]


def history(user, ut):
    return list(Attempt.objects.filter(user=user, unit_test=ut, submitted_at__isnull=False).order_by("-submitted_at"))


def export(user):
    """This app's part of /me/export: every test attempt and answer."""
    out = []
    for a in Attempt.objects.filter(user=user).select_related("unit_test__unit").order_by("started_at"):
        out.append({"id": str(a.pk), "unit": a.unit_test.unit.legacy_path if a.unit_test else None,
                    "started_at": a.started_at.isoformat(),
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                    "score": str(a.score) if a.score is not None else None,
                    "max_score": str(a.max_score) if a.max_score is not None else None,
                    "answers": [{"question": n, "answer": r.answer, "correct": r.correct}
                                for n, r in _numbered(a)]})
    return out


def _numbered(a):
    responses = {r.question.uid: r for r in a.responses.select_related("question")}
    return [(i, responses[u]) for i, u in enumerate(a.question_uids, 1) if u in responses]
