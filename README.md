# NRSTATLAB Learn

The Django web application for the NRSTATLAB study site. Visitors read everything free. Signed-in
learners keep their progress, take a unit test after each unit, sit old papers, and see how ready
they are for their exam.

- **The plan:** `content/Webapp/` (in the content repository): `BUILD-GUIDE.md`,
  `ARCHITECTURE.md` and `PROMPT.md`.
- **The content:** `content/` is the static site, added as a git submodule. Content is written
  there, never here.

## Run it locally

```bash
git clone --recurse-submodules <this repo> && cd nrstatlab-learn
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                      # then edit SECRET_KEY
docker compose up -d db                   # or a local PostgreSQL 16
python manage.py migrate
python manage.py import_site              # loads the site from content/
python manage.py import_questions         # then its question bank and solved papers
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
- **Phase 3, unit tests:** the question bank (950 questions, the doubtful keys never scored) and a
  ten-question test on each unit that has enough checked questions. `docs/PHASE-3-REPORT.md`.
