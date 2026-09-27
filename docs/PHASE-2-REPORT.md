# Phase 2 report: Accounts and progress

**Status:** done, awaiting review. **Date:** 27 September 2026.

## Done when (BUILD-GUIDE Phase 2)

| Criterion | Result |
|---|---|
| Sign-up sends a verification email (console backend in development) | **Met.** Tested; the email links to `/accounts/confirm-email/` and its subject starts "NRSTATLAB:" |
| Login is rate-limited after 5 failed attempts | **Met, twice over.** django-axes locks the email from that address at the fifth failure (a 429 page, for an hour); allauth's own limit also refuses the sixth. The right password does not get in |
| Export and delete work in an end-to-end test | **Met.** Export holds only the learner's own data; deletion removes the user, profile, progress, events and email addresses, anonymises attempts and sends one email |
| Progress marked on one browser shows on another | **Met, in Chromium.** A unit marked on one device shows as done on a second, and an undo there reaches the account |
| An import of mixed valid and invalid ids reports both correctly | **Met.** `{"imported": n, "already": n, "ignored": [...]}`, tested with valid, invalid, duplicate and oversized lists |

## What was built

### Accounts (Step 7)

- **Sign-up** asks for a display name, the email, a password, "I am 18 or over" and "I have read the
  privacy notice". Nothing else. Email and Google sign-up go through the same form.
- **Email verification** is mandatory. Mail goes through `EMAIL_URL`: the console in development,
  any SMTP service in production, where the setting is required.
- **Google sign-in** appears only when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set.
  Tokens are not stored.
- **Lockout.** django-axes reads the email address (allauth passes it as `email`, which axes did
  not see until it was told to). Successful sign-ins are not logged.
- **`/me/export`** downloads everything kept, as JSON. Each app adds its part through
  `accounts.services.register_exporter`, so `accounts` imports no other app.
- **`/me/delete`** asks for the password, or for DELETE on an account without one (Google only).
  It emails a confirmation, signs the learner out and deletes the account. Test attempts stay,
  with no user.
- **Admin second factor.** With `ADMIN_OTP_REQUIRED` (on by default in production), `/staff/` needs a
  TOTP code. `manage.py add_totp_device <email>` issues one.
- **The Site record** is named NRSTATLAB, with the host from `SITE_ORIGIN`, so emails never say
  example.com.
- **`/privacy.html`** says in plain words what is kept and why, what the two cookies do, the
  failed-sign-in records, who else handles data, and how to export or delete. Contact is through
  GitHub Issues only.

### Progress (Step 8)

- **`progress.services` is the only writer** of `UnitProgress` and `ActivityEvent`.
  - Marking moves a unit between "not started" and "studied".
  - A passed unit is never changed by marking or by an import.
  - An import brings units in as "studied", never "passed", and never lowers a status. It accepts
    at most 400 ids of at most 300 characters.
- **Endpoints** (login and CSRF required, JSON): `POST /me/progress/studied`,
  `POST /me/progress/import` and `POST /me/progress/import/dismiss`.
- **The dashboard, `/me/`,** shows:
  - the next unit, and the last one marked done;
  - each course in progress, with a bar ("3 of 5 units done");
  - the streak, counted in India time;
  - the account links (email, password, export, privacy, delete, sign out).
  Test scores, weak topics and readiness arrive with Phases 3 and 5; until then no placeholder is
  shown.

### How the site's pages learn about the account

The site already has its own progress script. `content/assets/progress.js` draws every mark from
one browser entry, `nrstatlab.progress.v1`: the unit toggles, the ticks on course homes and the
home-page totals. The application reuses it rather than rewriting it.

- **`apps/core/inject.py`** adds two fragments to each served page, both between
  `<!-- nrstat-learn -->` markers:
  - the account link, as the last item of the site bar: "Sign in", or "My progress";
  - in `<head>`, the account state as JSON (escaped like `json_script`) and `static/learn/learn.js`.
- **`learn.js`** runs before `progress.js`, which is deferred.
  - **On the first sign-in in a browser,** it sets the guest's entry aside, and offers once per
    account to bring its pages over ([Bring over] / [Not now]).
  - **While signed in,** it writes the account's progress into the entry and sends each press of
    "Mark this unit done" to the server. If a save fails it says so under the button. A unit
    whose test is passed stays done.
  - **On signing out,** it puts the guest's own progress back, so a shared computer never shows
    the last learner's progress.

  The account is told apart by an opaque id, never the email. Every storage access is guarded.
- **App pages** (dashboard, sign-in, privacy) use the site's own bar, footer and stylesheets. They
  add `static/learn/app.css`, with a dark theme.

## Checks run

| Check | Result |
|---|---|
| pytest | **80 passed**, coverage 96%: accounts 17, progress 25, page injection 9, browser 6, pages 11 (the Phase 1 page tests now run for a guest and for a learner), importer 10, dependencies 2 |
| Every page, with the marked fragments removed, is the original file | 675 indexed and 18 other pages, byte-identical, for a guest and for a learner |
| Account link | Exactly one on each of the 676 pages with the site bar; none on the 16 pages without it |
| JSON cannot break out of its script tag | A page id containing `</script><script>` is escaped |
| Browser journey (pytest-playwright, Chromium, live server) | Guest progress stays local. Sign-in offers "2 pages"; Bring over imports them. A toggle reaches the account. A second device sees the same ticks and is not asked again. Sign-out restores the guest's progress and clears the markers. Not now closes the offer for good. A failed save says so. A passed unit stays done |
| Content repository's browser checks, against Django, as a guest | site nav (39 loads, 3 viewports), sections, home, progress: all pass. Contrast: 42,670 text elements, 0 below WCAG AA |
| Contrast on the app pages (sign-up, sign-in, unit with banner, dashboard, privacy, delete, email, password), light and dark | 2,144 text elements, 0 below AA |
| Site bar height with the account link, 360 to 1280 px | Unchanged at every width (78 px on phones, 40 to 45 px wider); no horizontal overflow. On phones and tablets the link is an icon beside the search |
| HTTP crawl of all 675 pages | 1 broken target, the same known false positive as Phase 1 (a stylesheet named in a code example) |
| `ruff`, `check`, `check --deploy`, migrations | Clean. `check --deploy` warns only about the placeholder `SECRET_KEY`; production refuses to start without `EMAIL_URL` |
| `git -C content status` | Empty: the content submodule is untouched (and the test checks it) |

**Mutation checks.** Each rule was broken on purpose, and a test failed each time, for the right
reason:

| Broken on purpose | Caught by |
|---|---|
| The closing injection marker | the stripped-equals-original tests |
| "A passed unit is never changed" | `test_a_passed_unit_is_never_changed_by_marking` |
| "An import never lowers a status" | `test_import_never_lowers_a_status_or_passes_a_unit` |
| CSRF on `/me/progress/studied` | `test_endpoints_enforce_csrf` |
| `json_script` escaping | `test_the_state_cannot_break_out_of_its_script_tag` |
| learn.js restoring the guest's progress | `test_the_whole_journey` (browser) |
| learn.js sending each toggle | `test_the_whole_journey` (browser) |
| Deletion (deactivate instead of delete) | `test_delete_removes_everything_and_anonymises_attempts` |

## Found and fixed during the phase

- **A passed unit with no dates was sent as done `""`,** and `progress.js` reads an empty value as
  not done. The browser test caught it; every done unit now always carries a date.
- **django-axes did not see the email,** because allauth passes it as `email`, not `username`. The
  lockout test caught it; `AXES_USERNAME_CALLABLE` now reads it.
- **CI could not install** (run #3): pytest-playwright 0.7.1 needs pytest below 9. Locally, pip had
  downgraded pytest to 8.4.2 without saying so. It is now pytest-playwright 0.9.0, and the suite
  runs on pytest 9.1.1.

## Changes from the plan (recorded in ARCHITECTURE §13)

- **The route is `POST /me/progress/studied`,** with the page id in the JSON body, instead of
  `/me/progress/<unit_id>/studied` with HTMX. The button belongs to `progress.js`, which knows the
  page id.
- **The dependency graph gains `core → progress`,** and every app may use `accounts.services`.
- **The email provider and the Google OAuth client move to "before staging (Phase 7)".** The code
  works with any SMTP service and any Google client, so nothing waits on them.

## Screenshots (`docs/phase2/`)

| Page | Phone (390 px) | Wide (1280 px) |
|---|---|---|
| Sign-up | `signup-390.png` | `signup-1280.png` |
| Sign-in | `signin-390.png` | `signin-1280.png` |
| Unit page, with the import offer | `unit-banner-390.png` | `unit-banner-1280.png` |
| Unit page, signed in | `unit-signed-in-390.png` | `unit-signed-in-1280.png` |
| Dashboard | `dashboard-390.png`, `dashboard-dark-390.png` | `dashboard-1280.png` |
| Privacy | `privacy-390.png` | `privacy-1280.png` |

## For the owner (content, not changed here)

- **`about.html` says progress is "kept in this browser and nowhere else … this site has none".**
  That is true on GitHub Pages but not in the app. Its "Clear my progress" button also clears only
  the browser; a signed-in learner's progress comes back from the account on the next page. It
  needs wording for the app before launch. `assets/progress.js` has the same sentence in a comment,
  which is harmless.
- **The home page's UGC NET card** still says "each answer explained rather than just marked",
  flagged in Phase 1.
- **Before staging:** an email provider (SPF, DKIM and DMARC on `<domain>`) and a Google OAuth
  client; the privacy page names the hosting and email companies once they are chosen.

## Next

Phase 3 (unit tests) waits for approval.
