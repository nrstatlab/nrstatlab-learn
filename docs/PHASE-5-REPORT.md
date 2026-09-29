# Phase 5 report: Readiness for your exam

**Status:** done, awaiting review. **Date:** 29 September 2026.

Everything here runs on a computer only. Nothing is online until the owner signs off
`docs/LOCAL-CHECK.md`, which now has a Phase 5 section (checks 5.1–5.8).

## Done when (BUILD-GUIDE Step 12)

| Criterion | Result |
|---|---|
| A test fixture with known passes gives the hand-computed readiness | **Met.** A five-line exam, with links of known depth and one unit passed, one only studied, a line taught only on a course home page and a line not taught, gives **55.6%** = (1 + 2/3 + 0) / 3, written as a literal in the test |
| The same on real data | **Met.** CSIR NET with UGC NET Unit II and Theory of Probability Unit 1 passed gives **26.9%**, worked by hand from `csirmap.py` (below) |
| Only passed units count (the owner's decision) | **Met.** A studied unit is shown and counts nothing; a test proves it, and a mutation that counts it is caught |
| The readiness page | **Met.** The figure; how many of the exam's units have a test, and the most that can be reached today; every syllabus line with its units, their status and a bar; the lines taught only on pages with nothing to mark, and the lines not taught here, listed plainly; the next three units to study |
| CI | CI_RESULT |

## The arithmetic, as built

```
weight(link)   = 2 if deep else 1
item_readiness = Σ weight × [unit passed] / Σ weight     over the line's links to markable units
exam_readiness = mean of item_readiness over the lines with at least one such link
```

- **Link depth.**
  - UGC NET lines link to two kinds of page. The UGC NET unit's own section is **brief**, as the map
    grades it. A course unit whose text the map generator has checked is **deep**.
  - Every other map grades each line, and its links take that grade.
- **Left out of the figure, and listed:**
  - 16 lines taught only on a page with nothing to mark: a course home page, a guide or self-study
    notes;
  - 58 lines not taught on this site.
- **The ceiling** is the same arithmetic with every unit that has a unit test counted as passed.

**CSIR NET by hand.** 39 lines count; 4 are page-only and 9 are not here.
- UGC NET Unit II is the only unit link of ten of those lines: Unit 1, lines 1, 2, 3, 5, 6, 9, 12,
  13, 15 and 16. Each scores 1.
- Theory of Probability Unit 1 shares Unit 4, line 2 with UGC NET Unit I. Both links are deep, so
  that line scores 1/2.
- (10 + 1/2) / 39 = **26.9%**. With UGC NET Unit II alone, 10 / 39 = **25.6%**, the step the browser
  test and check 5.6 see.

## The five exams

| Exam | Lines | Counted | Page only | Not here | Units needed | With a test | Highest today |
|---|---|---|---|---|---|---|---|
| UGC NET Statistics | 130 | 130 | 0 | 0 | 72 | 12 | 50.8% |
| CSIR NET Mathematical Sciences | 52 | 39 | 4 | 9 | 23 | 7 | 56.4% |
| ASRB NET Agricultural Statistics | 99 | 73 | 3 | 23 | 70 | 2 | 2.1% |
| ISS | 147 | 112 | 9 | 26 | 92 | 9 | 7.7% |
| APPSC | 73 (both posts share them) | 73 | 0 | 0 | 39 | 9 | 35.6% |

The plan estimated UGC NET's ceiling at 62.9%, before link depths were applied. With the UGC NET
units at exam level (weight 1) and the course units in depth (weight 2), it is 50.8%. The tested
units are mostly the UGC NET units.

## What was built

- **The syllabus import** (`apps/core/syllabus.py`, run by `import_site`):
  - It reads each map through the content repository's own generator, from the row functions that
    print the map pages. So the wording and grades are the map's own, and the generators' own checks
    run on every import:
    - ISS: `iss_map.rows_of`;
    - ASRB NET: `asrb_map.build_rows`;
    - UGC NET: `ugc_map.build_rows`;
    - APPSC: `appsc_map.all_rows`;
    - CSIR NET: `csirmap.UNIT*`.
  - Links are followed through redirect stubs, and every link must be a page of the site.
  - The 501 lines are stored with their groups (`ExamPaper`) and links (`SyllabusLink`, with the unit
    where there is one). The counts are checked after writing.
  - A re-import changes nothing, and a dropped line is deleted.
- **Readiness** (`apps/examinations/readiness.py`), reached through `examinations.services`:
  - `readiness`, `summary`, `set_target`, `clear_target` and `target_of`;
  - the arithmetic is pure functions, tested without a database.
- **Routes** (signed in):

  | Route | What it does |
  |---|---|
  | `/readiness/` | the five exams, with your figure for each |
  | `/readiness/<exam>/` | the readiness page |
  | `POST /readiness/<exam>/target` | make this my exam, or stop (a form post; your own only) |

- **Next to study:**
  - units not yet passed, ranked by how many of the exam's lines they teach, then by course order;
  - a studied unit with no test is skipped, as nothing more can be done there;
  - each gives its step: "Study it, then take its test", "Take its test", or "Study it; its test is
    not written yet".
- **On the site's pages:**
  - each exam's map pages (the hub, and the ISS paper and APPSC post pages) get a box after the site
    bar: your figure and the most reachable today, or "Sign in to see your readiness";
  - it is drawn by `learn.js` outside `main`, as in Phases 3–4.
- **Dashboard and data:**
  - The dashboard gets a "Your exam" card: the figure, the ceiling and the next unit, or "Choose the
    exam you are preparing for".
  - `progress` gains a small card registry, so it imports no app that depends on it.
  - The data export includes the target exam.
- **The offline kit:** the learner with progress prepares for UGC NET, so the card and the page show
  a figure at once: **4.1%**.

## Checks run

| Check | Result |
|---|---|
| pytest | **185 passed**, coverage 95%. Readiness 22, browser 13 (1 new: follow the box on the CSIR NET map, pass a test, see 0% become 25.6%, make it your exam, see the card), and the 162 from before (two extended: the importer's idempotence test and setup_local's demo learner) |
| Mutation checks | **8 of 8 caught** (below) |
| The offline checklist, walked in Chromium against a fresh `docker compose` stack | **45 of 45 pass**: Phases 1–4 as before, the eight new Phase 5 checks, and the lockout last |
| Contrast, light and dark: three exam maps with the box (guest and learner), the exams list, three readiness pages, the dashboard with the card | **9,212 text elements, 0 below WCAG AA** |
| The content repository's browser checks, against Django | site nav (39 loads), sections, home, progress: all pass; contrast 42,716 elements, 0 below AA |
| HTTP crawl of all 675 pages | the same single known false positive as Phases 1–4 |
| Every page, stripped of the app's fragments, is still the original | yes, for a guest and a learner |
| `ruff check`, `manage.py check`, migrations check (none needed), both import dry runs | clean |
| `git -C content status` | empty |

| Broken on purpose | Caught by |
|---|---|
| Depth weights ignored | `test_a_fixture_exam_gives_the_hand_computed_readiness` |
| Studied counted as passed | the same |
| Page-only lines counted as 0 | the same |
| Not-here lines counted as 0 | the same |
| An old address not followed to its unit | `test_an_old_address_is_followed_to_its_unit` |
| Next units by course order only | `test_the_next_units_serve_the_most_lines_then_follow_course_order` |
| A studied unit without a test not skipped | the same |
| "Stop preparing" on another exam clears yours | `test_the_target_is_only_ever_your_own` |

## Found and fixed during the phase

- **Page titles were stored with HTML entities** (73 pages, 52 of them units). Unit titles read "Real Analysis &amp;amp;
  Matrix Algebra" wherever the app showed them: the dashboard's "Continue where you left off", test
  results, and now readiness. This dated from Phase 2.
  - Titles are now stored as text, and a changed title is enough to update a page on import.
  - The served pages are unaffected: they keep their own `<title>`, byte for byte.
- **Exam names** were the hubs' page titles, such as "ISS Syllabus Map" and "UGC NET Statistics
  Study Material". They are now the names the site's own menu gives them (`site_nav_model.label_of`,
  as the menu calls it): ISS, UGC NET Statistics.
- **A figure showed as "0%" in the box and "0.0%" on the page.** Both now print a whole number
  without ".0".

## Changes from the plan (recorded in ARCHITECTURE §16)

- **No migration was needed.** The Phase 1 models held everything.
- **The step for an untested unit not yet studied** reads "Study it, then take its test", which is
  more precise than the plan's "Study it".
- **`study.services.titles`** was added, so a page-only link shows its page's title.
- **UGC NET's ceiling is 50.8%, not 62.9%**, as explained above.

## Screenshots (`docs/phase5/`)

Each at 390 px and 1280 px, in light and dark (`-390`, `-1280`, `-390-dark`, `-1280-dark`).

| Page | Files |
|---|---|
| The UGC NET map with the box, guest and learner | `map-guest-*.png`, `map-learner-*.png` |
| Readiness: the figure and the next units | `readiness-*.png` |
| Readiness: lines with their units and statuses | `readiness-lines-*.png` |
| Readiness: the page-only and not-here lists (ISS) | `readiness-lists-*.png` |
| The five exams | `exams-*.png` |
| The dashboard's "Your exam" card | `dashboard-*.png` |

## For the owner (content, not changed here)

1. **Every ceiling rises with more unit tests.** 148 units teach a line of some exam, and 19 of them
   have a test. The untested units that teach the most lines, across the exams:
   - Econometrics Unit 5: 8 lines (ASRB, ISS, UGC);
   - Computational Statistics and R Unit 1: 8 (ISS, UGC);
   - Multivariate Analysis Unit 2: 7;
   - Linear Algebra and Linear Models Units 1 and 4: 7 each;
   - Inferential Statistics Unit 5: 7 (four exams);
   - Estimation Theory Unit 1: 7;
   - Design and Analysis of Experiments (advanced) Unit 1: 7.

   Each needs at least ten checked, published questions (decision 8), the same content work as
   Phase 3.
2. **16 lines are taught only on pages with nothing to mark**, such as course home pages, "Which
   test?" and the machine-learning self-study notes. Pointing the map at a unit, where one teaches the
   line, would bring them into the figure.
3. **58 lines are not taught on this site** (ISS 26, ASRB 23, CSIR 9), as each map already says.
4. **ASRB NET and ISS readiness can reach only 2.1% and 7.7% today.** Their pages say so plainly. They
   are the exams that gain most from item 1.

## Next

Phase 6 (the quality loop: item statistics and review) waits for approval.
