"""The question bank (BUILD-GUIDE Step 9): counts match their sources, every key is one
of its question's own options, and the keys in doubt can never be scored."""
import json

import pytest
from django.core.management import call_command

from apps.assessments import services as assessments
from apps.assessments.models import Question, QuestionUnit
from apps.core.questions import CONTESTED
from apps.papers.models import PaperQuestion, SolvedPaper

pytestmark = pytest.mark.django_db
SOURCES = {"ugc-mcq-": 500, "ugc-2026-": 150, "appsc-aso-2025-": 150, "appsc-aso-2022-": 150}


def test_each_source_is_read_and_stored_in_full(bank):
    for prefix, n in SOURCES.items():
        assert bank.count(prefix) == bank.expected[prefix] == n, prefix
        stored = assessments.bank_counts(prefix)
        assert stored["total"] == n and stored["retired"] == 0, (prefix, stored)
    assert Question.objects.count() == sum(SOURCES.values())


def test_every_key_is_one_of_its_own_options():
    wrong = []
    for q in Question.objects.prefetch_related("choices"):
        correct = [c.label for c in q.choices.all() if c.is_correct]
        withdrawn = q.flag_reason.startswith("Withdrawn by the Commission")
        if (withdrawn and correct) or (not withdrawn and len(correct) != 1) or len(q.choices.all()) != 4:
            wrong.append((q.uid, correct))
    assert not wrong, wrong[:5]


def test_stored_keys_are_the_sources_keys(bank):
    stored = {q.uid: q for q in Question.objects.prefetch_related("choices")}
    for items in bank.sources.values():
        for item in items:
            q = stored[item["uid"]]
            assert [c.label for c in q.choices.all() if c.is_correct] == [c[0] for c in item["choices"] if c[2]]
            assert q.stem_html == item["stem_html"]


def test_the_six_contested_keys_are_flagged_with_the_audits_reason():
    for (unit, n), reason in CONTESTED.items():
        q = Question.objects.get(uid=f"ugc-mcq-u{unit:02d}-q{n:02d}")
        assert q.status == Question.FLAGGED and reason in q.flag_reason and "AUDIT-2026-09" in q.flag_reason
    assert Question.objects.filter(uid__startswith="ugc-mcq-", status=Question.FLAGGED).count() == 6


def test_the_withdrawn_questions_are_marked_on_their_papers():
    withdrawn = {(pq.paper.slug, pq.number) for pq in PaperQuestion.objects.filter(withdrawn=True)}
    assert withdrawn == {("appsc-aso-2025-paper-ii", 134), ("appsc-aso-2022-paper-ii", 51), ("appsc-aso-2022-paper-ii", 81)}
    for pq in PaperQuestion.objects.filter(withdrawn=True):
        assert "discrepancy" in pq.withdrawn_note and pq.official_key == ""
        assert pq.question.status == Question.FLAGGED


def test_warning_notes_on_solved_pages_flag_their_questions():
    assert Question.objects.filter(uid__startswith="ugc-2026-", status=Question.FLAGGED).count() == 7
    assert "Var(Y)" in Question.objects.get(uid="ugc-2026-q070").flag_reason
    assert Question.objects.get(uid="appsc-aso-2022-q138").status == Question.FLAGGED


def test_questions_without_a_unit_link_stay_out_of_unit_tests():
    assert not QuestionUnit.objects.filter(question__uid__startswith="ugc-2026-").exists()
    for q in Question.objects.filter(uid__startswith="appsc-", unit_links__isnull=True):
        assert "Study this" not in q.solution_html  # nothing to link to


def test_appsc_questions_link_to_the_unit_their_solved_page_names(bank):
    for prefix in ("appsc-aso-2025-", "appsc-aso-2022-"):
        for item in bank.sources[prefix]:
            linked = list(QuestionUnit.objects.filter(question__uid=item["uid"]).values_list("unit__legacy_path", flat=True))
            assert linked == item["units"], item["uid"]


def test_ugc_mcqs_link_to_their_ugc_net_unit():
    q = Question.objects.get(uid="ugc-mcq-u07-q03")
    assert list(q.unit_links.values_list("unit__legacy_path", flat=True)) == ["exams/ugc-net/unit7.html"]


def test_comprehension_passages_go_with_the_five_questions_they_serve():
    with_passage = sorted(int(q.uid[-3:]) for q in Question.objects.filter(uid__startswith="ugc-2026-",
                                                                           stem_html__contains='class="comp"'))
    assert with_passage == [1, 2, 3, 4, 5, 46, 47, 48, 49, 50, *range(141, 151)]


def test_papers_carry_only_what_their_own_header_says():
    appsc = SolvedPaper.objects.get(slug="appsc-aso-2025-paper-ii")
    assert (appsc.duration_minutes, appsc.marking_scheme) == (150, {"correct": 1, "wrong": -0.33})
    assert "docs/sources/appsc-aso-2025-paper-ii.pdf" in appsc.duration_source
    assert appsc.questions.count() == 150 and str(appsc.held_on) == "2025-04-29"
    ugc = SolvedPaper.objects.get(slug="ugc-net-june-2026")
    assert ugc.duration_minutes is None and ugc.marking_scheme is None and ugc.questions.count() == 150


def test_a_second_import_changes_nothing(capsys):
    call_command("import_questions")
    out = capsys.readouterr().out
    for prefix in SOURCES:
        assert f"{prefix}: 0 created, 0 updated, {SOURCES[prefix]} unchanged, 0 retired" in out


def test_a_review_decision_stands_until_the_source_changes(bank):
    item = next(i for i in bank.sources["ugc-mcq-"] if i["uid"] == "ugc-mcq-u05-q50")
    Question.objects.filter(uid=item["uid"]).update(status=Question.PUBLISHED)   # the owner settles it
    assessments.store_questions(bank.sources["ugc-mcq-"], prefix="ugc-mcq-")
    assert Question.objects.get(uid=item["uid"]).status == Question.PUBLISHED
    changed = [dict(i, stem_html=i["stem_html"] + " (reworded)") if i is item else i for i in bank.sources["ugc-mcq-"]]
    assessments.store_questions(changed, prefix="ugc-mcq-")
    assert Question.objects.get(uid=item["uid"]).status == Question.FLAGGED   # edited: back to review


def test_a_question_the_source_drops_is_retired_not_deleted(bank):
    items = bank.sources["ugc-mcq-"][1:]
    assert assessments.store_questions(items, prefix="ugc-mcq-")["retired"] == 1
    assert Question.objects.get(uid="ugc-mcq-u01-q01").status == Question.RETIRED


@pytest.mark.parametrize("bad", [
    {"choices": [("A", "x", False), ("B", "y", False)]},                      # no key
    {"choices": [("A", "x", True), ("A", "y", False)]},                       # repeated label
    {"qtype": "numeric", "answer_text": "about 3", "choices": []},
    {"qtype": "match", "answer_text": json.dumps({"A": "III"}),
     "choices": [("A", "x", False, "left"), ("I", "y", False, "right")]},     # pairs with nothing
    {"units": ["index.html"]},                                                # not a unit
])
def test_the_bank_refuses_a_question_whose_key_is_not_its_own(bad):
    item = {"uid": "t-1", "qtype": "single", "stem_html": "s", "choices": [("A", "x", True)], "units": []} | bad
    with pytest.raises(assessments.BankError):
        assessments.store_questions([item], prefix="t-")
    assert not Question.objects.filter(uid="t-1").exists()
