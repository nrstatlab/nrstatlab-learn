# Phase 3 report: Unit tests

**Status:** done, awaiting review. **Date:** 27 September 2026.

## Done when (BUILD-GUIDE Phase 3)

| Criterion | Result |
|---|---|
| The counts match their sources | **Met.** Each source is read at the count it states, stored at that count, and checked again after storing: 500 + 150 + 150 + 150 = 950 questions |
| The six flagged keys can never be scored (a test proves it) | **Met.** They are never drawn, and even when forced into an attempt they count neither for nor against. A mutation test shows the check has teeth |
| Unit tests pass for every question type | **Met.** Single, multiple, numeric (with tolerance), assertion-reason and match, each scored right when right and wrong when wrong |
| Unlocking | **Met.** A test opens only when the unit is studied (or passed) and has at least ten published questions |
| Retake selection | **Met.** Unseen questions come first: four retakes of a 49-question unit draw 40 different questions, and the fifth takes the last nine unseen |
| No answers in the HTML before submit | **Met.** No key, working or source order of the options is in the test page; options are named by tokens made for each attempt |
| CI | **Green on GitHub.** Run #7 on `df51875` passed every step, including the question import dry run and the browser tests: 132 passed, 95% coverage |

## The question bank (Step 9)

`python manage.py import_questions` (after `import_site`; `--dry-run` reads and checks only):

| Source | Read as | Questions | Published | Flagged | Linked to a unit |
|---|---|---|---|---|---|
| UGC NET MCQs (`exams/ugc-net/mcqs.html`) | ten units of 50; key is the answer's first letter | 500 | 494 | 6 | 500 (their UGC NET unit) |
| UGC NET June 2026 paper (`exams/ugc-net/solved-2026.html`) | key in "Answer: (D)"; four comprehension passages, each with the five questions after it | 150 | 143 | 7 | 0 |
| APPSC ASO Paper-II 2025 | through the site's own generator, `tools/exams/appsc_paper.py` | 150 | 140 | 10 | 129 |
| APPSC ASO Paper-II 2022 | the same | 150 | 136 | 14 | 135 |
| Practice sets on unit pages | searched; none has answers | 0 | | | |

- **Key checks.**
  - The UGC NET keys were all recomputed in the September audit, except the six it contested; each
    question records that in its `recompute_log`.
  - The APPSC keys are the Commission's own, as marked in its papers.
- **Never scored.** 37 questions are flagged:
  - the six keys the audit contested, with its words as the reason;
  - every question whose solved page carries a warning note (7, 9 and 12 notes);
  - the three the Commission withdrew (2025 Q134; 2022 Q51 and Q81). These are also marked
    `withdrawn` on their paper, with the Commission's note.
- **Unit links.**
  - UGC NET MCQs go to their UGC NET unit.
  - APPSC questions go to the page their "Study this" link names.
  - The 2026 paper names no unit for any question, so its questions stay in the exam bank and are
    never drawn for a unit test.
- **Solved papers.** Three are stored with their 450 questions, for Phase 4. Duration and marking
  come only from the paper's own header, with the source recorded. The 2026 page records neither,
  so none is claimed.
- **Re-importing** changes nothing that has not changed.
  - A status set in the admin (a flagged question the owner has settled, say) stands until the
    source edits that question.
  - A question the source drops is retired, never deleted.
- **19 unit tests open today:**
  - all ten UGC NET units;
  - Descriptive Statistics Units 2–4;
  - Statistical Methods Unit 2;
  - Applied Statistics Unit 1;
  - Economics Units 1, 5 and 6;
  - Financial Accounting Unit 1.

  25 more units have some questions but fewer than ten.

## The test engine (Step 10)

- **Drawing.**
  - Published questions of the unit only.
  - Unseen first, then the rest.
  - Round-robin across difficulty bands: item statistics once a question has 30 answers (Phase 6),
    else the author's estimate, else "unrated". No question has a rating yet.
  - Shuffled from the attempt's seed, so a reload shows the same test.
- **One open attempt per test**, enforced by a database constraint as well as in code.
- **Answers** are saved one by one as they are chosen (`POST /test/attempt/<id>/answer`, JSON). The
  form also posts every answer on submit, so the page works without script. It adds answers but
  never clears one.
- **Scoring** is on the server. A question flagged after the draw counts neither for nor against,
  and the result says how many did not count.
- **A pass** (at or above 70%) marks the unit passed. The best score is kept, every attempt stays
  in history, and retakes are always open.
- **Results** show:
  - the score;
  - every question with the learner's answer, the key and the working;
  - links back to the unit and the course.
- **The unit page** gains a box under its lower "Mark this unit done":
  - for a guest, "Sign in to take it";
  - "It opens when you mark this unit done";
  - "Take the test", "Carry on with the test" or "Take the test again", with the best score.

  The box appears even when browser storage is blocked.
- **The dashboard** lists the last five tests. The streak now counts a day with a test taken too.
- **Exports** include every attempt and answer. After a deletion, attempts stay with no user.

## Checks run

| Check | Result |
|---|---|
| pytest | **132 passed**, coverage 95%. Bank 19, unit tests 30, browser 9 (3 new), and the 74 from Phases 1–2 |
| Mutation checks | **13 of 13 caught** (below) |
| MathJax on every open test | 19 units × 6 draws: 1,865 formulas typeset on test and result pages, no TeX left raw, no MathJax error (MathJax served locally, as the sandbox blocks its CDN) |
| Contrast, light and dark: unit page with the box, test intro, test, result, dashboard | 3,859 text elements, 0 below WCAG AA |
| The content repository's browser checks, against Django | site nav (39 loads), sections, home, progress: all pass; contrast 42,686 elements, 0 below AA |
| HTTP crawl of all 675 pages | the same single known false positive as Phases 1–2 |
| Every page, stripped of the app's fragments, is still the original | yes, for a guest and a learner |
| `git -C content status` | empty |

| Broken on purpose | Caught by |
|---|---|
| Flagged questions let into the draw | `test_the_draw_takes_published_questions_of_the_unit_only` |
| Voiding at submit removed | `test_the_contested_keys_can_never_be_scored` |
| Tokens replaced by option labels | `test_the_test_page_gives_no_answer_away` |
| A submitted attempt left open to change | `test_a_submitted_attempt_cannot_change` |
| The owner check removed | `test_only_the_owner_can_see_or_answer_an_attempt` |
| Opening before the unit is studied | `test_a_test_opens_only_after_the_unit_is_studied` |
| Seen questions first | `test_a_retake_draws_unseen_questions_first` |
| "Multiple" scored on a subset | `test_every_question_type_scores_wrong_when_wrong` |
| Numeric tolerance made exclusive | `test_a_numeric_answer_on_the_tolerance_is_right` |
| Pass only above 70% | `test_a_pass_marks_the_unit_passed_and_a_fail_does_not` |
| The form clearing saved answers | `test_the_whole_flow_through_the_pages` |
| Contested keys imported unflagged | `test_the_six_contested_keys_are_flagged_with_the_audits_reason` |
| A key outside its options accepted | `test_the_bank_refuses_a_question_whose_key_is_not_its_own` |

## Found and fixed during the phase

- **Submitting the form cleared answers saved by the page script** when a field was missing from the
  post. The form now only adds answers. The flow test found it; the mutation test keeps it fixed.
- **The test box first sat outside the page's progress block.** The content repository's own checks
  caught two things:
  - the section check counted the box as page text;
  - the nav check found its link in a colour other than the site's.

  It now sits inside the lower "Mark this unit done" block and uses the site's link colour, and
  both checks pass.
- **On the test page, the site's form-label style stacked each option vertically.** The option
  layout rule was made specific enough to win.

## Changes from the plan (recorded in ARCHITECTURE §14)

- **Answers are saved with a small script and JSON**, not HTMX, as in Phase 2. There is also a plain
  form, which works without script.
- **`progress.services.record_test`** replaces `mark_passed`. It is called for every submitted test:
  - it keeps the best score;
  - a pass marks the unit passed;
  - it records the test for the dashboard and the streak.

  This lets `progress` show recent tests without importing `assessments`.
- **The dependency graph gains `core → assessments`**, for the test box on unit pages.
- **The solved papers are imported now** (Step 9, point 3), because their withdrawn questions are
  marked on them. Practice and exam mode remain Phase 4.

## Screenshots (`docs/phase3/`)

| Page | Phone (390 px) | Wide (1280 px) |
|---|---|---|
| Unit page, guest | `unit-guest-390.png` | `unit-guest-1280.png` |
| Unit page, test open | `unit-open-390.png`, `unit-open-390-dark.png` | `unit-open-1280.png` |
| A test in progress | `test-390.png`, `test-390-dark.png` | `test-1280.png` |
| Result | `result-390.png`, `result-question-390.png`, dark versions | `result-1280.png`, `result-question-1280.png` |
| Dashboard with tests | | `dashboard-1280.png` |

The maths in the screenshots shows as TeX because the sandbox blocks the MathJax CDN. The render
check above shows it typesets.

## For the owner (content, not changed here)

1. **The 28 flag notes.** Each keeps its question out of tests until you publish it in the admin
   (Questions → filter by status → flagged). A first reading:
   - **Only the printing is loose; the key is clear:** 2025 Q68, Q69, Q84, Q87, Q96, Q112; 2026 Q70,
     Q90, Q144, Q150; 2022 Q83, Q119, Q123.
   - **The key itself is arguable:** 2025 Q129, Q143, Q148; 2026 Q34, Q42, Q134; 2022 Q10, Q24,
     Q39, Q80, Q107, Q127, Q133, Q138, Q140.
2. **The six contested UGC NET keys** (audit §5, item 1) are still yours to settle, on the site page
   and here.
3. **The UGC NET MCQ keys lean heavily on A:** A 262, B 192, C 34, D 12 of 500. The app shuffles the
   options, so it cannot be gamed there. On the site page, a reader who always picks A scores over
   half.
4. **291 of the 310 units have no test yet.** New questions are content work (Step 9, point 5):
   - an author drafts;
   - a script recomputes the numbers;
   - a second reviewer checks (decision 8);
   - then the question is published.
5. **The 2026 paper names no unit per question.** Adding a unit to each would bring 143 more checked
   questions into the UGC NET unit tests.
6. **Deployment** needs `import_questions` after `import_site`. MathJax loads from the same CDN as
   the site's pages; self-hosting it is for Phase 7.

## Next

Phase 4 (old papers: practice and exam mode) waits for approval.
