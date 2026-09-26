# Phase 1 report: Foundations

**Status:** done locally, awaiting review. **Date:** 26 September 2026.

## Done when (BUILD-GUIDE Phase 1)

- **All 675 indexed paths return 200 with the same content: met, and exceeded.** Each page is
  byte-identical to the original file, not just the same text.
- **Every old address returns 301: met.** All 946, each to a page that returns 200.
- **CI: written** (`.github/workflows/ci.yml`). It runs ruff, `check`, `check --deploy`, the
  migrations check, the import dry run and pytest. It has not run on GitHub yet, because the
  repository could not be created from this session.

## What was built

| Step | Result |
|---|---|
| 1 Repository | Local repository `nrstatlab-learn`; content submodule at `content/`; `.gitignore`; `.env.example` |
| 2 Project | Django 5.2.17 LTS; project `config`; 7 apps in `apps/`; settings split into base, dev, test, prod |
| 3 Custom user | `accounts.User` (email login, no username) and `Profile`, in the first migration |
| 4 Dev environment | `docker-compose.yml` (PostgreSQL 16) and a `Dockerfile`, both validated; developed against a local PostgreSQL 16 |
| 5 Models and import | Every model from ARCHITECTURE §4, all in the admin; `import_site` with `--dry-run` and `--files-only`; idempotent; stored counts checked against the counts read |
| 6 Pages at old paths | A catch-all view; 301s; folders served as on GitHub Pages; the site's 404 page; site files through WhiteNoise at their old paths; the domain move is two settings |

**Import:**

| Imported | Count |
|---|---|
| Courses | 56 |
| Markable units | 310 |
| Indexed pages | 675 |
| Other pages still served (lab demos, 404, archive) | 18 |
| Redirects | 946 |
| Exams | 5 |
| Site files | 622 |

A second run changes nothing.

## Checks run

- **pytest: 20 passed.** Coverage is 94% overall: importer 93%, views 100%, services 94%.
  - Every indexed page is byte-identical; the other 18 pages still work.
  - Every redirect is a 301 to a live page.
  - Folders behave as on GitHub Pages; the 404 page is served with its paths rewritten.
  - Every site file is served byte-identical.
  - The import is idempotent and refuses a count mismatch.
  - Stub targets resolve; the origin rewrite works.
  - The dependency graph is respected and has no cycles.
  - The content submodule is left exactly as checked out.
- **Mutation tests.** Each of these was made to fail on purpose, and each was caught:
  - a page off by one character;
  - a 302 instead of a 301;
  - `study` importing `core`;
  - `core` importing `study.models`.
- **The content repository's own browser checks, run against the Django server.** All pass:
  - site nav: 39 loads, 3 viewports;
  - sections, home and progress;
  - contrast: 42,614 elements, 0 below WCAG AA.
- **HTTP link crawl through Django.** 675 pages and 725 distinct link targets, with 1 failure:
  the known false positive (a `styles.css` inside a code sample on the Web Technologies Unit 2
  page).
- **`check --deploy` with the prod settings.** Only the warning about the placeholder secret key,
  which is expected.
- **Screenshots** at 390 px and 1280 px of the home page and a unit: no horizontal scroll.

## Incident, found and fixed within the phase

`django-admin startproject config .` runs the Black formatter over its whole target directory when
Black is installed, and the target held the content submodule.
- **What happened.** Black reformatted 264 Python files inside `content/`. No HTML page was touched,
  so no stored page was ever wrong. 188 of the files are served (lab programs), and until the fix
  their served copies were the reformatted versions.
- **The fix.** The submodule was restored to its pinned commit, and the served copies were
  re-copied from the originals.
- **The guard.** A test now fails if the submodule's `git status` is not empty; a one-line edit
  makes it fail. The importer also no longer writes bytecode into the submodule.
- **Nothing reached any remote.** The content repository's own clone was never affected.

## Decisions taken during the phase

1. **Navigation.** It is stored and served verbatim, not re-rendered from `site_nav_model`. That
   keeps every page byte-identical. Phase 2 adds the account link into the stored navigation.
2. **Importer location.** It lives in `core`, and each app stores its own tables through its
   `services`. The dependency test caught the first version breaking this.
3. **Exam targets and paper attempts.**
   - The exam a learner is preparing for is `examinations.ExamTarget`, not a Profile field, so
     `accounts` depends on nothing.
   - Paper attempts link through `papers.PaperAttempt`, so `assessments` never imports `papers`.
   - The graph gains `papers → examinations`.
4. **Import timing.** The question bank and syllabus maps are imported in the phases that use them
   (Phase 3 and Phase 5), not in Phase 1.
5. **The 18 unindexed pages** (lab demos, `404.html`, the archive page) are still served, because
   today's site serves them.

## Open

- **The GitHub repository does not exist yet.** Creating it was refused (403: the session's
  GitHub connection cannot create repositories). All work is committed locally and pushes as soon
  as the owner creates an empty private `nrstatlab/nrstatlab-learn` and gives Claude access.
- **`sitemap.xml` and `robots.txt`** are still served as the content repository's files, for the
  current origin. Generating them for the new domain is Phase 7 work.
