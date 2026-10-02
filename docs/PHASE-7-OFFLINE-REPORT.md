# Phase 7 report, the offline part: ready for launch, on the computer

**Status:** done, awaiting review. **Date:** 29 September 2026.

The owner chose to build now everything for launch that can be built and checked on a computer.
**Nothing is online:**
- no host, no domain, no staging address;
- no link from the live site.

The rest of Phase 7 is the owner's choices, then staging and going live (`docs/DEPLOY.md`, "Decisions
still open"). `docs/LOCAL-CHECK.md` gains checks 7.1 and 7.2.

## Done (BUILD-GUIDE Step 16, the parts that need no host)

| Criterion | Result |
|---|---|
| MathJax self-hosted | **Met.** MathJax 3.2.2, Apache-2.0 with its licence, in `static/vendor/mathjax` (9.3 MB): the two builds the pages load, the TeX extensions, the CHTML fonts and the accessibility menu. The 256 pages that name the CDN are pointed at it as they are served, and the app's own pages load it with their settings in a file. **Formulas now draw with the internet off** |
| A strict Content Security Policy | **Met,** on every response, enforced (not report-only), on the computer as in production. Below |
| `check --deploy` clean | **Met,** with the production settings, even at `--fail-level WARNING` |
| `pip-audit` | **No known vulnerabilities** in `requirements.txt`. CI now runs it on every push |
| Authorisation checked on every view that takes an id | **Met.** `tests/test_authorisation.py`, below |
| Logging with no personal data in it | **Met.** Production logs to the console at INFO; request bodies are never logged. A test signs in with a wrong password and then the right one, and finds neither in the log |
| A 500 page | **Met.** `templates/500.html`, in the site's style, needing nothing from the database |
| Backups and a restore rehearsal | **Met offline:** `pg_dump` to `./backups`, start again from nothing, `pg_restore`, and `manage.py data_counts` agrees before and after (check 7.2). The production schedule is in `docs/DEPLOY.md` |
| The nightly `item_stats` | **Ready for the host:** the cron line, and what it needs, in `docs/DEPLOY.md` |
| The coverage gate (Step 15) | **Met.** CI fails below 90% for the scoring and progress apps. They are at 96% |
| The two browser flows Step 15 lists that were missing | **Met,** each at 390 px and 1280 px: fail a unit test, retake it and pass; download my data, then delete the account |
| CI | **Green on GitHub.** Run #16 on `c9f5d63` passed every step: lint, the Django checks and `check --deploy`, migrations, both import dry runs, the full suite with the browser tests, the new 90% coverage gate, and the new `pip-audit`. Run #17 then failed `pip-audit` on a newly published advisory (below); **run #18, on `1b9a92c`, is green** with the fix |

## The Content Security Policy, as built (`apps/core/csp.py`)

**The application's own pages** (sign-in, the dashboard, tests, papers, readiness, the admin):

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data:; font-src 'self'; connect-src 'self';
frame-ancestors 'none'; object-src 'none'; base-uri 'self';
form-action 'self' https://accounts.google.com
```

- `'unsafe-inline'` for styles only, because MathJax writes its own styles.
- No template has an inline script or an inline handler; a test keeps it so.

**The site's pages** get the same policy, and `script-src` gains exactly what that page runs, read
from its HTML as served:
- the **hash of each inline script it runs**: MathJax settings, equation numbering, the 404 page's
  path fix, and the lab demos written as modules. JSON-LD and other data blocks are never run, and
  get no hash;
- its **inline handlers** (`onclick`, `onsubmit`), by hash, with `'unsafe-hashes'`. Four pages have
  them;
- the **outside libraries** four lab and notes pages load:
  - Mermaid from jsDelivr, on two Data Science units;
  - Prism from cdnjs and Google Fonts, on the archived Machine Learning notes;
  - jQuery, on one Web Technologies lab;
- the one outside **API** a page's own script calls: the weather demo's.

The page's bytes are not changed, so every page is still served as it was written; the policy goes
in the header beside it. It is worked out once per page and kept in memory.

## The authorisation review

Every route that takes a parameter is in a table in `tests/test_authorisation.py`, with how it is
protected. A new one fails the test until it is added.

| Kind | Routes | Checked |
|---|---|---|
| An attempt or a sitting, by its id | the unit test's attempt, answer, submit and result; the paper's sitting, answer, check, reveal, submit and review (10) | Signed out: sent to sign in. **Another learner: 404**, for GET and POST alike. The owner: 200 |
| A unit, a paper or an exam, by its id or slug | the test's intro and start, the paper's rules and start, readiness and its target (6) | Sign-in needed; each acts on the signed-in learner's own data only |
| allauth's one-time keys | email confirmation, password reset (2) | The key is the credential, as allauth designs it |
| The site's pages | the catch-all | Public |
| Every POST | the 6 POSTs among the 10 above, 3 more with a parameter, and 4 without (studied, import, dismiss, delete the account) | **403 without the CSRF token** |
| The admin | `/staff/`, a question, the review queue, a learner's account, the attempts | A learner is sent to the staff sign-in |

**Findings: none needed fixing.** Every id route already checked its owner and answered 404 to
anyone else, so an id reveals nothing, not even that it exists.

## Checks run

| Check | Result |
|---|---|
| pytest | **232 passed**, coverage 96%: Phase 7's 14 launch tests, 5 authorisation tests, 4 browser runs (two flows at two widths), and the 209 from before |
| Mutation checks | **4 of 4 caught** (below) |
| The CSP crawl, in Chromium, with every request that leaves the computer refused | **All 693 site pages**, then 25 application pages as a learner, a guest and the owner: the dashboard, a unit test, a paper exam and practice, readiness, sign-in, the admin and its review page. **0 CSP violations, 0 script errors.** MathJax started on 261 pages with 0 errors. The only requests refused were the four pages' outside libraries |
| The paper questions, fully offline | **450 questions, 2,431 formulas typeset, 0 problems,** on the exam page and the review of all three papers, with nothing fetched from outside |
| The offline checklist, walked in Chromium against a fresh `docker compose` stack | **55 of 55 pass**: Phases 1–6, the two new Phase 7 checks, and the lockout last |
| `ruff check`, `manage.py check`, `check --deploy` (production settings), migrations check, both import dry runs | clean |
| `pip-audit -r requirements.txt` | no known vulnerabilities |
| The content repository's checks, and contrast in both themes | all pass; 42,614 text elements, 0 below WCAG AA |
| The HTTP crawl | 675 pages, all 200. One "broken" link, as in every phase: a code sample's `href="styles.css"`, which is text, not a link |
| `git -C content status` | empty |

| Broken on purpose | Caught by |
|---|---|
| The MathJax rewrite dropped | `test_no_served_page_names_the_mathjax_cdn` |
| A page's inline-script hash left out | `test_a_site_page_allows_exactly_its_own_inline_scripts` |
| The owner check removed from the test result route | `test_an_attempt_is_only_ever_its_owners` |
| CSRF exempted on the test's submit | `test_every_post_needs_the_csrf_token` |

## Found during the phase

- **The four pages with outside libraries still need the internet for their demonstrations** (Mermaid
  diagrams, Prism highlighting, jQuery, one font). The CSP allows them on those pages only. The rest of
  each page works offline. Serving them from the app too is possible, as for MathJax; it is listed for
  the owner below, since it changes what those pages load.
- **Checking a review for raw `$…$` text needs care.** An APPSC economics question prices things in
  dollars (`$5,000`). Those amounts are real text, marked so MathJax leaves them alone, and the checks
  skip them.

- **The new `pip-audit` step caught a fresh advisory within two days.** Run #17, on a docs-only
  commit, failed it. GHSA-xpv3-w29h-x7cv was published after run #16: a timing leak in oauthlib's
  provider-side PKCE check. This app is only an OAuth client and never runs that code, but the fix is
  simple. django-allauth 65.19.6 is allauth's own security release for it, and requires oauthlib 4.0.0.
  Its one incompatible change is in the Bitbucket and Pinterest providers, which are not used here.
  Upgraded from 65.19.4; the full suite, the checks and `pip-audit` pass again.

## After the phase: the review queue closed (2 October 2026)

The owner reviewed all 37 questions the app held back from scoring. The rule given was to take the
right option among those printed, whatever the Commission's key says, with a genuine explanation.
The decisions, question by question, are in the content repository's `docs/AUDIT-2026-09.md` §5.1.

**The answers:**
- **8 answers changed:**
  - UGC NET MCQs: Unit 3 Q39 B, Unit 5 Q50 A, Unit 7 Q14 B, Unit 8 Q16 A;
  - APPSC 2025: Q143 2;
  - APPSC 2022: Q10 1, Q127 1, Q138 4.
- **2 questions the Commission withdrew are answered:** 2022 Q51 (2) and Q81 (1). They now count
  everywhere, timed exam included.
- **APPSC 2025 Q134 has no correct option** (r ± PE gives 0.769 and 0.631). It is stored retired, so
  it is never drawn and never scored, and the paper shows "Not counted. No option is correct".
- **26 answers stand.** Every warning note on the solved pages is folded into a working that stands
  on its own, and the pages no longer mention the old keys.

**What changed in the app:**
- `apps/core/questions.py` no longer hard-codes the contested six. APPSC questions take the right
  answer from the generator (`ANSWERS`, `NO_CORRECT` in its data files). A question with no correct
  option carries `scorable: False`. `official_key` keeps the paper's own mark, for the record.
- `apps/assessments/bank.py` stores a question that cannot be scored as retired. It no longer
  re-imports a retired question on every run.
- **The paper pages say "Not counted"**, with the reason, where they said "Withdrawn by the
  Commission". The review tags the right answer as "the right answer", not "the official key".
- **The content submodule** points at the content commit that settles the answers.

**What follows from it:**
- No question imports as flagged; the review queue holds only what reviewers or the statistics put
  there.
- APPSC 2025 counts 149 questions, APPSC 2022 and UGC NET June 2026 all 150.
- The settled answers gave Applied Statistics Unit 3 its tenth published question, so **20 units
  have a unit test**.
- The readiness ceilings rise for APPSC (35.6% → 41.8%) and ISS (7.7% → 9.5%).

**Checks:**

| Check | Result |
|---|---|
| pytest | **235 passed**, coverage 96%: six new tests for the settled answers, three retired with the contested and flagged sets they checked, and the expectations the change moves updated |
| Mutation checks | **4 of 4 caught**: the settled answers ignored; a question with no correct option imported as published; a retired question re-imported on every run; the no-correct-option note dropped |
| The content rechecks | Both pages held to their PDFs with exactly the recorded exceptions: 1,050 and 896 checks, 0 failures. A changed answer the page does not show is caught |
| The changed checks of `LOCAL-CHECK.md`, walked in Chromium against a fresh `setup_local` database | **20 of 20 pass**: 3.8, 3.9, 4.2–4.8, 6.1–6.8 and the four demo sign-ins. The full 55-check walk script was lost when the container restarted, so the rest was not re-walked; the full test suite, the browser tests included, covers it |
| MathJax on the four changed pages, served offline by the app | 6,300 formulas, 0 errors |
| ruff, `check`, `check --deploy`, migrations, both import dry runs, `pip-audit` | clean |
| The content repository's checks and contrast | all pass |

## For the owner

1. **Walk 7.1 and 7.2** in `docs/LOCAL-CHECK.md`: formulas with Wi-Fi off, and a backup and restore.
2. **Choose the host, the domain and the email provider** (`docs/DEPLOY.md`, "Decisions still open").
   Everything else for staging is written down there, ready.
3. **Optional:** serve Mermaid, Prism and jQuery from the app, so that those four pages' demonstrations
   work offline too. Say if you want it.

## Next

The online part of Phase 7 waits for your choices and for your sign-off of `docs/LOCAL-CHECK.md`:
staging, a restore test there, then the soft launch.
