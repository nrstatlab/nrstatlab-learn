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
python manage.py runserver
```

## Test

```bash
pytest                                    # unit tests, every legacy path, dependency rules
ruff check .
```
