# Phase 4 report: Old papers, in practice mode and exam mode

**Status:** done, awaiting review. **Date:** 28 September 2026.

Everything here runs on a computer only. Nothing is online until the owner signs off
`docs/LOCAL-CHECK.md`, which now has a Phase 4 section (checks 4.1–4.10).

## Done when (BUILD-GUIDE Step 11)

| Criterion | Result |
|---|---|
| A learner can practise a solved paper one question at a time | **Met.** Answer, then **Check my answer**: right or not, the key, the working, and "Study this". **Show the solution** works without answering. Previous, Next and "Go to question". The place is kept. It works without script |
| A learner can sit a paper as an exam, under the paper's own rules | **Met.** The whole paper on one page, in its sections. A bar that stays in view shows answered N of M and, where the paper records a duration, the time left. A grid of question numbers. The clock is fixed at the start, survives a reload or a second tab, and submits the paper at zero |
| Only what a paper's header records is claimed | **Met.** Timer and marking come from the header, with the source named on the rules page. The UGC NET 2026 page records neither, so there is no timer and nothing is taken off, and the rules page says so |
| The score is right | **Met.** The done-when test sits APPSC 2025: 100 counted questions right, 20 wrong, and Q134 and the doubtful questions answered too. It scores **93.40 of 140.00**, computed by hand from `content/tools/exams/appsc_paper_2025.json` and the flag list, not from app code |
| Withdrawn and doubtful questions do not count (the owner's decision) | **Met.** Q134 (2025), and Q51 and Q81 (2022), are shown greyed with the Commission's note and cannot be answered. Questions whose key the solved page doubts count neither for nor against, and the review says why for each. A doubtful key the owner publishes in the admin counts from then on |
| The review | **Met.** The score, the maximum and the percentage; totals by section (right, wrong, blank, not counted, marks), which add up to the score; "N questions did not count"; then every question with the learner's answer, the official key, the working and "Study this" |
| CI | CI_RESULT |

## The rules each paper runs under

| Paper | Timer | Marking | Counted |
|---|---|---|---|
| APPSC ASO Paper-II 2025 | 150 min, from the question paper's header | +1 / −0.33, blank 0, from the header and each question's marks line | 150 − 1 withdrawn − 9 doubtful = **140** |
| APPSC ASO Paper-II 2022 | 150 min, the same | +1 / −0.33, the same | 150 − 2 withdrawn − 12 doubtful = **136** |
| UGC NET June 2026 | none: the page records no duration | none recorded: each counted question is one mark, nothing taken off | 150 − 7 doubtful = **143** |

"Counted" is decided when a paper is submitted, and stored with the sitting. So a review always shows
the rules it was scored under, even after the owner settles a key.

## What was built

- **Data** (one migration each):
  - `papers.PaperQuestion.section`, filled by the importer. APPSC sections are the syllabus
    groups of the site's own generator: Economics, Financial Accounting, Statistics, Computers.
    UGC 2026 has Paper I (Q1–50) and Paper II (Q51–150).
  - `papers.PaperAttempt` gains `deadline`, `position`, `revealed` and `not_counted`.
- **`assessments`** (reached only through its services):
  - A paper keeps its printed option order and labels (1–4 for APPSC, A–D for UGC). Options are
    still named by per-attempt tokens, so the page gives nothing away.
  - `start_paper`, `grade`, `close`, `reveal` (practice only) and `review_items`. Unit-test
    `submit` now uses the same `grade`, so a doubtful question is treated the same way everywhere.
- **`papers`**: services, views, templates and `static/learn/exam.js` (the tally, the grid and
  the clock).
- **Routes:**

  | Route | What it does |
  |---|---|
  | `/papers/` | the three papers, with your last result for each |
  | `/papers/<slug>/` | the rules; **Practise** / **Carry on practising**, **Sit the paper** / **Carry on with the exam** |
  | `POST /papers/<slug>/start` | one open sitting per mode per paper |
  | `/papers/attempt/<id>/` | the exam page, or one practice question (`?q=n`) |
  | `POST …/answer` | JSON; refused after the deadline plus 30 s, and for a withdrawn question |
  | `POST …/check` | practice, as a form: saves the answer and reveals (or reveals only, "Show the solution") |
  | `POST …/reveal` | practice, JSON |
  | `POST …/submit` | scores and freezes; a late form counts only what was saved in time |
  | `/papers/attempt/<id>/review` | the review |

  All need sign-in, and a sitting is only ever its owner's.
- **On the site's pages:** each solved paper page gets a box after the site bar: "Try this paper
  yourself … (150 questions, 150 minutes, −0.33 for a wrong answer)", with **Practise or sit it**,
  or **Sign in to practise or sit it**. It is drawn by `learn.js` from the account state, outside
  `main`, so the site's own section and link checks are unaffected.
- **Progress:** `progress.services.record_paper` puts each exam sat on the dashboard ("Old papers",
  each score linking to its review) and counts it towards the day streak. Practice is not recorded
  as a sitting.
- **The offline kit:** the learner with progress (`progress.learner@localhost`) now has APPSC 2025
  sat as an exam: 90 right and 30 wrong, **80.10 of 140.00**.

## Checks run

| Check | Result |
|---|---|
| pytest | **162 passed**, coverage 94%. Papers 21, browser 12 (3 new: sit APPSC 2025 from its solved page, practise UGC 2026 and come back to the same place, the clock submitting the paper), setup_local 5 (1 new), and the 137 from before |
| Mutation checks | **8 of 9 caught**; the ninth is equivalent (below) |
| The offline checklist, walked in Chromium against a fresh `docker compose` stack | **37 of 37 pass**: Phases 1–3 as before, the ten new Phase 4 checks, and the lockout last |
| MathJax on every paper question | 450 questions on the exam page and on the review: **2,431 formulas typeset, no TeX left raw, no MathJax error** (MathJax served locally, as the sandbox blocks its CDN) |
| Contrast, light and dark: solved page with the box, papers index, rules, exam, review, practice with the answer shown, dashboard | **19,606 text elements, 0 below WCAG AA** |
| The content repository's browser checks, against Django | site nav (39 loads), sections, home, progress: all pass; contrast 42,698 elements, 0 below AA |
| HTTP crawl of all 675 pages | the same single known false positive as Phases 1–3 |
| Every page, stripped of the app's fragments, is still the original | yes, for a guest and a learner |
| `ruff check`, `manage.py check`, migrations check, both import dry runs | clean |
| `git -C content status` | empty |

| Broken on purpose | Caught by |
|---|---|
| Negative marks dropped | `test_appsc_2025_in_exam_mode_scores_as_computed_by_hand` |
| A withdrawn question counted | `test_a_withdrawn_question_never_counts_even_if_published_by_mistake` |
| A doubtful question counted | `test_appsc_2025_in_exam_mode_scores_as_computed_by_hand` |
| A withdrawn question answerable | `test_appsc_2025_in_exam_mode_scores_as_computed_by_hand` |
| The deadline not enforced | `test_after_the_time_no_answer_is_saved_and_only_what_was_saved_counts` |
| The owner check removed | `test_only_the_owner_can_touch_a_sitting` |
| Reveal allowed in exam mode | `test_reveal_is_for_practice_only` |
| A paper's options shuffled | `test_the_paper_keeps_its_printed_order_and_labels` |
| Late form answers counted (the view's own guard removed) | not caught, and cannot be: the service refuses late answers too, so the page behaves the same. The guard stays, as a second line |

## Found and fixed during the phase

- **Two mutations first survived**, a withdrawn question counted and a paper's options shuffled,
  because no test published a withdrawn question or looked at the option order. Two tests were
  added, and both mutations are now caught.
- **A withdrawn question's options stacked** their numbers above the text on a phone. They now sit
  on one line, as the answerable options do.
- **The section table had no header row group.** It now has `thead` and `tbody`, with column and
  row headers, so a screen reader reads each number with its section and column.
- **Not a defect:** the MathJax check first flagged 2025 Q49 ("earning $5,000 … save $400"). Those
  are dollar amounts, which the site's generator wraps so MathJax leaves them alone, exactly as on
  the solved page.

## Changes from the plan (recorded in ARCHITECTURE §15)

- **`grade` and `close`** replace the planned `mark`. Unit-test `submit` is rebuilt on them, so both
  kinds of attempt share one scoring core.
- **`not_counted` is stored with each sitting**, so a review never changes after the event.
- **Practice works without script:** **Check my answer** and **Show the solution** are form posts
  (`…/check`). The JSON `…/reveal` is there too.
- **The solved-page box has one button**, to the rules page, where the learner chooses practice or
  exam, rather than two.
- **`setup_local` gives the demo learner a sat paper**, so the dashboard and the review can be
  checked at once.

## Screenshots (`docs/phase4/`)

Each at 390 px and 1280 px, in light and dark (`-390`, `-1280`, `-390-dark`, `-1280-dark`). Maths is
typeset: the screenshots serve MathJax locally.

| Page | Files |
|---|---|
| Solved page, the box for a guest and a learner | `solved-guest-*.png`, `solved-learner-*.png` |
| Rules, APPSC 2025 and UGC 2026 | `rules-*.png`, `rules-ugc-*.png` |
| Exam: the bar, the clock and the grid | `exam-*.png` |
| Exam: Q134, withdrawn | `exam-withdrawn-*.png` |
| Review: score and sections | `review-*.png` |
| Review: a question not counted | `review-not-counted-*.png` |
| Practice, the answer checked | `practice-*.png` |
| The papers, and the dashboard | `papers-1280.png`, `dashboard-1280.png` |

## For the owner (content, not changed here)

1. **The 28 doubtful keys** (9 + 12 + 7) are out of every score until you publish them in the admin
   (Questions → filter by status → flagged). Once published, a key counts from the next submission,
   in unit tests and in papers. `docs/PHASE-3-REPORT.md`, "For the owner", sorts them into
   printing-only and arguable keys.
2. **UGC NET June 2026 has no timer and no negative marking** because its page records neither.
   To add them, name the official source, and they will be recorded with it.
3. **"Study this" links:**
   - none of the 150 UGC 2026 questions has one (the page names no unit per question);
   - 21 APPSC 2025 and 15 APPSC 2022 questions have none.

   Their reviews say "Not taught on this site yet".

## Next

Phase 5 (readiness for your exam) waits for approval.
