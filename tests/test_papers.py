"""Old papers (BUILD-GUIDE Step 11): practice mode, exam mode under the paper's own rules,
and the review. The done-when test sits the APPSC 2025 paper and checks its score against
a hand computation made from the paper's own data, not from the application's code."""
import importlib.util
import json
import re
import sys
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.assessments import engine
from apps.assessments.models import Question
from apps.papers import services as papers
from apps.papers.models import PaperAttempt, SolvedPaper
from apps.progress.models import ActivityEvent

pytestmark = pytest.mark.django_db
APPSC25, APPSC22, UGC26 = "appsc-aso-2025-paper-ii", "appsc-aso-2022-paper-ii", "ugc-net-june-2026"


def appsc_2025_source():
    """The paper's key and the solved page's flags, read straight from the content repository."""
    exams = settings.CONTENT_DIR / "tools" / "exams"
    raw = json.loads((exams / "appsc_paper_2025.json").read_text(encoding="utf-8"))
    key = {q["n"]: q["key"] for q in raw["questions"]}
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("_hand_appsc_data", exams / "appsc_paper_data.py")
        data = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data)
    finally:
        sys.dont_write_bytecode = before
    flagged = {n for n, (_t, _w, flag) in data.SOLUTIONS.items() if flag}
    return key, flagged


def sit(learner, slug, mode="exam"):
    return papers.start(learner, SolvedPaper.objects.get(slug=slug), mode)


def tok(sitting, n, label):
    return engine.token(sitting.attempt, sitting.attempt.question_uids[n - 1], "option", label)


def wrong_label(sitting, n):
    q = Question.objects.get(uid=sitting.attempt.question_uids[n - 1])
    return q.choices.filter(is_correct=False).first().label


def right_label(sitting, n):
    q = Question.objects.get(uid=sitting.attempt.question_uids[n - 1])
    return q.choices.get(is_correct=True).label


# ---------------------------------------------------------------- the done-when test

def test_appsc_2025_in_exam_mode_scores_as_computed_by_hand(learner, client):
    key, flagged = appsc_2025_source()
    counted = [n for n in sorted(key) if key[n] is not None and n not in flagged]
    assert len(counted) == 140 and 134 not in counted
    right, wrong = counted[:100], counted[100:120]
    hand = Decimal(len(right)) * Decimal("1") - Decimal(len(wrong)) * Decimal("0.33")   # 93.40
    assert hand == Decimal("93.40")

    s = sit(learner, APPSC25)
    for n in right:
        papers.answer(s, n, tok(s, n, str(key[n])))                   # the Commission's key, as printed (1-4)
    for n in wrong:
        papers.answer(s, n, tok(s, n, next(str(k) for k in (1, 2, 3, 4) if k != key[n])))
    for n in sorted(flagged - {134}):                                 # doubtful: answered, and must not count
        papers.answer(s, n, tok(s, n, wrong_label(s, n)))
    with pytest.raises(engine.BadAnswer):                             # withdrawn: cannot be answered
        papers.answer(s, 134, tok(s, 134, "1"))
    s = papers.submit(s)
    assert (s.attempt.score, s.attempt.max_score) == (hand, Decimal("140.00"))
    assert "134" in s.not_counted and s.not_counted["134"].startswith("Withdrawn by the Commission")
    assert len(s.not_counted) == 10

    client.force_login(learner)
    html = client.get(f"/papers/attempt/{s.attempt_id}/review").content.decode()
    assert "93.40 of 140.00" in html
    q134 = html.split('id="q134"')[1].split("</section>")[0]
    assert "not counted" in q134 and "discrepancy" in q134


def test_the_section_totals_add_up_to_the_score(learner):
    key, _ = appsc_2025_source()
    s = sit(learner, APPSC25)
    for n in range(1, 151):
        if key[n]:
            papers.answer(s, n, tok(s, n, str(key[n]) if n % 3 else wrong_label(s, n)))
    s = papers.submit(s)
    r = papers.review(s)
    assert sum(sec["marks"] for sec in r["sections"]) == s.attempt.score
    assert {sec["name"] for sec in r["sections"]} == {"Economics", "Financial Accounting", "Statistics", "Computers"}
    assert sum(sec["right"] + sec["wrong"] + sec["blank"] + sec["not_counted"] for sec in r["sections"]) == 150


def test_every_study_link_in_a_review_resolves(learner, client):
    s = papers.submit(sit(learner, APPSC22))
    client.force_login(learner)
    for item in papers.review(s)["items"]:
        if item["study"]:
            assert client.get("/" + item["study"]["path"]).status_code == 200, item["study"]


# ---------------------------------------------------------------- the rules

def test_each_paper_runs_under_only_what_its_header_records():
    r25, r22, r26 = (papers.rules(SolvedPaper.objects.get(slug=s)) for s in (APPSC25, APPSC22, UGC26))
    assert (r25["duration"], r25["wrong"], r25["counted"]) == (150, Decimal("-0.33"), 140)
    assert (r22["duration"], r22["counted"]) == (150, 136)
    assert [pq.number for pq in r22["withdrawn"]] == [51, 81]
    assert (r26["duration"], r26["scheme_recorded"], r26["wrong"], r26["counted"]) == (None, False, 0, 143)


def test_ugc_2026_has_no_clock_and_takes_nothing_off(learner):
    s = sit(learner, UGC26)
    assert s.deadline is None and papers.seconds_left(s) is None
    counted = [n for n in range(1, 151) if Question.objects.get(uid=s.attempt.question_uids[n - 1]).status == "published"]
    for n in counted[:10]:
        papers.answer(s, n, tok(s, n, right_label(s, n)))
    for n in counted[10:30]:
        papers.answer(s, n, tok(s, n, wrong_label(s, n)))
    s = papers.submit(s)
    assert (s.attempt.score, s.attempt.max_score) == (Decimal("10.00"), Decimal("143.00"))


def test_a_doubtful_key_settled_in_the_admin_counts_from_then_on(learner):
    Question.objects.filter(uid="appsc-aso-2025-q068").update(status="published")
    s = sit(learner, APPSC25)
    papers.answer(s, 68, tok(s, 68, right_label(s, 68)))
    s = papers.submit(s)
    assert s.attempt.max_score == Decimal("141.00") and s.attempt.score == Decimal("1.00")
    assert "68" not in s.not_counted


# ---------------------------------------------------------------- the clock

def test_the_clock_is_fixed_when_the_exam_starts(learner):
    s = sit(learner, APPSC25)
    assert s.deadline == s.attempt.started_at + timedelta(minutes=150)
    again = sit(learner, APPSC25)                                  # a reload, or a second tab
    assert again.pk == s.pk and again.deadline == s.deadline


def test_after_the_time_no_answer_is_saved_and_only_what_was_saved_counts(learner, client):
    key, _ = appsc_2025_source()
    s = sit(learner, APPSC25)
    papers.answer(s, 1, tok(s, 1, str(key[1])))
    PaperAttempt.objects.filter(pk=s.pk).update(deadline=timezone.now() - papers.GRACE - timedelta(seconds=1))
    s.refresh_from_db()
    with pytest.raises(papers.Late):
        papers.answer(s, 2, tok(s, 2, str(key[2])))
    client.force_login(learner)
    r = client.post(f"/papers/attempt/{s.attempt_id}/answer", json.dumps({"question": 3, "answer": tok(s, 3, str(key[3]))}),
                    content_type="application/json")
    assert r.status_code == 409
    client.post(f"/papers/attempt/{s.attempt_id}/submit", {"from_form": "1", "q4": tok(s, 4, str(key[4]))})
    s.attempt.refresh_from_db()
    assert s.attempt.score == Decimal("1.00")


def test_within_the_grace_an_answer_is_still_saved(learner):
    s = sit(learner, APPSC25)
    PaperAttempt.objects.filter(pk=s.pk).update(deadline=timezone.now() - timedelta(seconds=5))
    s.refresh_from_db()
    papers.answer(s, 1, tok(s, 1, right_label(s, 1)))
    assert s.attempt.responses.count() == 1


# ---------------------------------------------------------------- practice

def test_practice_shows_one_question_and_no_key_until_asked(learner, client):
    client.force_login(learner)
    s = sit(learner, UGC26, "practice")
    html = client.get(f"/papers/attempt/{s.attempt_id}/").content.decode()
    q1 = Question.objects.get(uid=s.attempt.question_uids[0])
    assert html.count('class="tq-options"') == 1 and "Check my answer" in html
    assert q1.solution_html[:40] not in html and "is-key" not in html
    # Check: the answer is saved and the key and working appear.
    client.post(f"/papers/attempt/{s.attempt_id}/check", {"q1": tok(s, 1, wrong_label(s, 1))})
    html = client.get(f"/papers/attempt/{s.attempt_id}/?q=1").content.decode()
    assert "Not quite." in html and "is-key" in html and "Working." in html
    # The place is kept.
    client.get(f"/papers/attempt/{s.attempt_id}/?q=7")
    s.refresh_from_db()
    assert s.position == 7 and s.revealed == [1]
    assert "Q7" in client.get(f"/papers/attempt/{s.attempt_id}/").content.decode()


def test_reveal_is_for_practice_only(learner, client):
    client.force_login(learner)
    exam = sit(learner, APPSC25)
    r = client.post(f"/papers/attempt/{exam.attempt_id}/reveal", json.dumps({"question": 1}), content_type="application/json")
    assert r.status_code == 409 and "after an exam is submitted" in r.json()["error"]
    with pytest.raises(engine.AttemptClosed):
        papers.reveal(exam, 1)
    practice = sit(learner, APPSC25, "practice")
    r = client.post(f"/papers/attempt/{practice.attempt_id}/reveal", json.dumps({"question": 5}),
                    content_type="application/json")
    assert r.json()["key"] == [right_label(practice, 5)]


def test_practice_is_not_recorded_as_a_sitting_on_the_dashboard(learner):
    papers.submit(sit(learner, UGC26, "practice"))
    assert not ActivityEvent.objects.filter(user=learner, kind="paper").exists()
    papers.submit(sit(learner, UGC26))
    assert ActivityEvent.objects.filter(user=learner, kind="paper").count() == 1


# ---------------------------------------------------------------- security

def test_the_exam_page_gives_no_key_or_working_away(learner, client):
    client.force_login(learner)
    s = sit(learner, APPSC25)
    html = client.get(f"/papers/attempt/{s.attempt_id}/").content.decode()
    assert html.count('<fieldset class="tq') == 150
    for word in ("is-key", "official key", "Working.", "appsc-aso-"):
        assert word not in html
    values = re.findall(r'type="radio" name="q\d+"\s+value="([^"]*)"', html)
    assert len(values) == 149 * 4 and all(re.fullmatch(r"[0-9a-f]{16}", v) for v in values)
    q2 = Question.objects.get(uid="appsc-aso-2025-q002")
    assert q2.solution_html[:40] not in html
    assert 'data-withdrawn="1"' in html.split('id="q134"')[1].split(">")[0] + ">"
    assert 'id="exam-clock"' in html


def test_only_the_owner_can_touch_a_sitting(client, make_learner):
    owner, other = make_learner("owner@example.com"), make_learner("other@example.com")
    s = sit(owner, APPSC25, "practice")
    client.force_login(other)
    base = f"/papers/attempt/{s.attempt_id}/"
    for url in (base, base + "review"):
        assert client.get(url).status_code == 404
    for url in (base + "answer", base + "reveal", base + "submit", base + "check"):
        assert client.post(url, "{}", content_type="application/json").status_code == 404
    assert s.attempt.__class__.objects.get(pk=s.attempt_id).submitted_at is None


def test_the_json_endpoints_need_the_csrf_token(learner):
    client = Client(enforce_csrf_checks=True)
    client.force_login(learner)
    s = sit(learner, APPSC25)
    r = client.post(f"/papers/attempt/{s.attempt_id}/answer", json.dumps({"question": 1, "answer": tok(s, 1, "1")}),
                    content_type="application/json")
    assert r.status_code == 403 and not s.attempt.responses.exists()


def test_a_submitted_paper_is_frozen(learner, client):
    s = papers.submit(sit(learner, APPSC25))
    with pytest.raises(engine.AttemptClosed):
        papers.answer(s, 1, tok(s, 1, "1"))
    client.force_login(learner)
    assert client.get(f"/papers/attempt/{s.attempt_id}/")["Location"].endswith("/review")


def test_signed_out_visitors_are_sent_to_sign_in(client):
    assert client.get(f"/papers/{APPSC25}/")["Location"].startswith("/accounts/login/")


# ---------------------------------------------------------------- the site's pages

STATE = re.compile(r'<script id="nrstat-account" type="application/json">(.*?)</script>', re.S)


def test_each_solved_page_offers_the_paper(client, learner):
    for slug in (APPSC25, APPSC22, UGC26):
        page = SolvedPaper.objects.get(slug=slug).page_path
        state = json.loads(STATE.search(client.get("/" + page).content.decode()).group(1))
        assert state["paper"]["url"] == f"/papers/{slug}/" and state["paper"]["sign_in"].endswith(f"/papers/{slug}/")
    state = json.loads(STATE.search(client.get("/exams/appsc/solved-2025-paper-ii.html").content.decode()).group(1))
    assert (state["paper"]["minutes"], state["paper"]["wrong"]) == (150, "0.33")
    client.force_login(learner)
    state = json.loads(STATE.search(client.get("/exams/ugc-net/solved-2026.html").content.decode()).group(1))
    assert state["paper"]["minutes"] is None and state["paper"]["wrong"] is None and "sign_in" not in state["paper"]


def test_the_pages_of_the_papers_flow(client, learner):
    client.force_login(learner)
    assert all(t in client.get("/papers/").content.decode() for t in ("APPSC", "UGC NET"))
    rules = client.get(f"/papers/{APPSC25}/").content.decode()
    assert "150 minutes" in rules and "-0.33 for a wrong one" in rules and "Q134" in rules
    r = client.post(f"/papers/{APPSC25}/start", {"mode": "exam"})
    s = PaperAttempt.objects.get(attempt__user=learner)
    assert r["Location"] == f"/papers/attempt/{s.attempt_id}/"
    assert "Carry on with the exam" in client.get(f"/papers/{APPSC25}/").content.decode()
    client.post(f"/papers/attempt/{s.attempt_id}/submit", {"from_form": "1", "q1": tok(s, 1, right_label(s, 1))})
    assert "Old papers" in client.get("/me/").content.decode()
    assert "1.00 of 140.00" in client.get("/me/").content.decode()


def test_a_withdrawn_question_never_counts_even_if_published_by_mistake(learner):
    Question.objects.filter(uid="appsc-aso-2025-q134").update(status="published")
    s = sit(learner, APPSC25)
    s = papers.submit(s)
    assert s.attempt.max_score == Decimal("140.00")
    assert s.not_counted["134"].startswith("Withdrawn by the Commission")


def test_the_paper_keeps_its_printed_order_and_labels(learner):
    s = sit(learner, APPSC25)
    for item in papers.view(s)[:20]:
        q = Question.objects.get(uid=s.attempt.question_uids[item["n"] - 1])
        printed = [c.text_html for c in q.choices.order_by("order")]
        assert [o["display"] for o in item["options"]] == ["1", "2", "3", "4"]
        assert [o["text_html"] for o in item["options"]] == printed
