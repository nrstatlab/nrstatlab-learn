"""UGC NET Paper I's model MCQs and syllabus map (content: exams/ugc-net/paper-1/).

The reader is tried on small pages written here, in the content's own markup, so
these tests hold whatever the content submodule carries: the owner approves Paper I
in batches, and until a batch is approved the published content has none of it."""
import pytest
from django.conf import settings

from apps.core import questions, syllabus

ROOT_PAGE = "exams/ugc-net/paper-1/mcqs.html"


def mcq(n, key="B", stem=None):
    return (f'<div class="mcq"><div class="q">{n}. {stem or f"Question {n}?"}</div>\n'
            f'<ol class="options"><li>w</li><li>x</li><li>y</li><li>z</li></ol>\n'
            f'<details><summary>Show Answer</summary><p>{key}. Because of the reason for question {n}.</p>'
            f'</details></div>\n')


def unit(n, body, k, approved=None):
    attr = f' data-approved="{approved}"' if approved else ""
    return (f'<div class="mcq-unit-head" id="unit{n}">\n<h2{attr}>Unit {n} — Title {n} ({k} MCQs)</h2>\n'
            f'<p>blurb</p>\n</div>\n{body}')


def passage(k, text="A short passage."):
    return f'<div class="comp" data-questions="{k}"><span class="clabel">Passage</span>\n<p>{text}</p>\n</div>\n'


@pytest.fixture
def page(tmp_path):
    def write(*units):
        path = tmp_path / ROOT_PAGE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html><body><main>" + "".join(units) + "</main></body></html>", encoding="utf-8")
        return tmp_path
    return write


def test_only_the_units_the_owner_approved_are_read(page):
    root = page(unit(1, mcq(1, "A") + mcq(2, "C"), 2, approved="2026-10-17"),
                unit(2, mcq(1) + mcq(2), 2))
    items, stated, held = questions.read_ugc_paper1_mcqs(root)
    assert [i["uid"] for i in items] == ["ugc-p1-mcq-u01-q01", "ugc-p1-mcq-u01-q02"]
    assert stated == 2 and held == [2]
    assert [c[0] for c in items[0]["choices"] if c[2]] == ["A"]
    assert items[1]["units"] == ["exams/ugc-net/paper-1/unit1.html"]
    assert "approved by the owner on 2026-10-17" in items[0]["recompute_log"]


def test_a_passage_goes_with_the_questions_it_serves_and_no_others(page):
    root = page(unit(3, passage(2, "Rivers.") + mcq(1) + mcq(2) + passage(1, "Forests.") + mcq(3), 3,
                     approved="2026-10-17"))
    items, _, _ = questions.read_ugc_paper1_mcqs(root)
    assert ["Rivers." in i["stem_html"] for i in items] == [True, True, False]
    assert ["Forests." in i["stem_html"] for i in items] == [False, False, True]


def test_a_passage_owed_more_questions_than_follow_it_is_refused(page):
    root = page(unit(3, passage(3) + mcq(1) + mcq(2), 2, approved="2026-10-17"))
    with pytest.raises(ValueError, match="owed 1 more"):
        questions.read_ugc_paper1_mcqs(root)


def test_a_count_or_numbering_that_disagrees_is_refused(page):
    with pytest.raises(ValueError, match="heading says 3 MCQs, found 2"):
        questions.read_ugc_paper1_mcqs(page(unit(1, mcq(1) + mcq(2), 3, approved="2026-10-17")))
    with pytest.raises(ValueError, match="question 2 is numbered 3"):
        questions.read_ugc_paper1_mcqs(page(unit(1, mcq(1) + mcq(3), 2, approved="2026-10-17")))


def test_an_unapproved_unit_is_not_checked_or_read_at_all(page):
    # a draft may be unfinished; it is the owner's approval that brings it into the bank
    root = page(unit(1, mcq(1), 1, approved="2026-10-17"), unit(2, mcq(1) + mcq(3), 5))
    items, stated, held = questions.read_ugc_paper1_mcqs(root)
    assert (len(items), stated, held) == (1, 1, [2])


def test_content_without_paper_1_gives_nothing(tmp_path):
    assert questions.read_ugc_paper1_mcqs(tmp_path) == ([], 0, [])
    assert syllabus.read_ugc_paper1(tmp_path, resolve=None) == []


def test_the_statistics_mcqs_read_as_before():
    items, stated = questions.read_ugc_mcqs(settings.CONTENT_DIR)
    assert stated == len(items) == 500
    assert items[0]["uid"] == "ugc-mcq-u01-q01" and not any('class="comp"' in i["stem_html"] for i in items)


def test_paper_1_groups_are_coded_apart_from_the_statistics_units(source):
    """When the content carries the Paper I map, its ten groups follow the Statistics paper's."""
    codes = [g["code"] for g in source.syllabus["ugc-net"]]
    assert codes[:10] == ["UI", "UII", "UIII", "UIV", "UV", "UVI", "UVII", "UVIII", "UIX", "UX"]
    assert codes[10:] in ([], [f"P1-U{r}" for r in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")])
