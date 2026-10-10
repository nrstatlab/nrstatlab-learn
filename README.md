# StatsTricks360 Learn

The Django web application for the StatsTricks360 study site. Visitors read everything free. Signed-in
learners keep their progress, take a unit test after each unit, sit old papers, and see how ready
they are for their exam.

- **The plan:** `content/Webapp/` (in the content repository): `BUILD-GUIDE.md`,
  `ARCHITECTURE.md` and `PROMPT.md`.
- **The content:** `content/` is the static site, added as a git submodule. Content is written
  there, never here.
- **Offline until sign-off.** Nothing of the app is online: no hosting, no staging, no domain.
  It is built and checked on a computer until the owner has signed off every check in
  [`docs/LOCAL-CHECK.md`](docs/LOCAL-CHECK.md).

## Try it on your computer

```bash
git clone --recurse-submodules https://github.com/nrstatlab/nrstatlab-learn.git && cd nrstatlab-learn
docker compose up --build                 # then open http://localhost:8000
```

That builds the app and prepares everything: the database, the site, the question bank and three
demo accounts. [`docs/LOCAL-CHECK.md`](docs/LOCAL-CHECK.md) lists the accounts and every check to
try.

## Develop

With Python 3.12 and a local PostgreSQL 16:

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                      # then edit SECRET_KEY and DATABASE_URL
python manage.py setup_local              # migrate, import_site, import_questions, demo accounts
python manage.py runserver
```

## Test

```bash
pytest                                    # unit tests, every legacy path, dependency rules, browser
ruff check .
pytest -m "not browser"                   # the same, without Chromium
```

Browser tests drive Chromium through pytest-playwright (`python -m playwright install chromium`
once). They run last, because a live server empties the test database after each one.

## Status

- **Phase 1, foundations:** every page of the site served at its old address. `docs/PHASE-1-REPORT.md`.
- **Phase 2, accounts and progress:** sign-up, progress kept on the account and shown by the site's
  own progress script, the dashboard, export and deletion. `docs/PHASE-2-REPORT.md`.
- **Phase 3, unit tests:** the question bank (950 questions, the doubtful keys never scored; 1,150 since UGC NET Paper I was
  approved on 3 October 2026) and a
  ten-question test on each unit that has enough checked questions. `docs/PHASE-3-REPORT.md`.
- **Phase 4, old papers:** the three solved papers, practised one question at a time or sat as an
  exam under each paper's own recorded rules, with a review by section. `docs/PHASE-4-REPORT.md`.
- **Phase 5, readiness:** each exam's syllabus map, line by line, with the units that teach each line;
  readiness from the units passed, the most reachable today, and the next units to study.
  `docs/PHASE-5-REPORT.md`.
- **Phase 6, the quality loop:** nightly item statistics (`manage.py item_stats`: p and r_pb, with
  questions that behave badly flagged for review), and the reviewers' queue in the admin, with the
  two-person rule and a history of every change. Approved 3 October 2026. `docs/PHASE-6-REPORT.md`.
- **Phase 7, the offline part:** MathJax served by the app, so the platform runs with the internet
  off; a strict Content Security Policy worked out per page; production logging and a 500 page; the
  authorisation review; backup and restore; `pip-audit` and the coverage gate in CI. Approved 3 October
  2026. `docs/PHASE-7-OFFLINE-REPORT.md`. What the host must do, and the owner's open decisions:
  `docs/DEPLOY.md`.
