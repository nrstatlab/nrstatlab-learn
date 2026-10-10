# Deploying StatsTricks360 Learn

**Not yet used.** Nothing is online until the owner signs off `docs/LOCAL-CHECK.md` and chooses the
host, the domain and the email provider (the open decisions, at the end). This page is what the
chosen host must do, written so that it fits any managed platform with PostgreSQL (ARCHITECTURE.md,
decision 2).

## What the host must provide

- **Python 3.12**, from `requirements.txt`. The server is `gunicorn config.wsgi`.
- **Managed PostgreSQL 16**, with daily backups kept 30 days (below).
- **HTTPS at the platform's proxy**, passing `X-Forwarded-Proto: https`. The app redirects HTTP to
  HTTPS and sends HSTS for a year, subdomains included, with `preload`: point only a domain meant to
  be HTTPS-only at it.
- **The content repository**, checked out beside the code as the `content/` submodule
  (`git clone --recurse-submodules`), at every deploy.
- **A daily scheduled job** (cron, or the platform's scheduler), for the item statistics.
- **Outbound SMTP**, for sign-up, password reset and the reviewers' email.

## Environment variables

| Variable | Value in production |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `SECRET_KEY` | 50 or more random characters, kept in the platform's secret store, never in git |
| `DATABASE_URL` | the managed database, `postgres://USER:PASSWORD@HOST:5432/NAME` |
| `ALLOWED_HOSTS` | the domain, e.g. `learn.example.org` |
| `SITE_ORIGIN` | `https://` and the domain: pages' canonical links and sitemap point here |
| `SITE_BASE_PATH` | `/` |
| `EMAIL_URL` | the provider's SMTP, e.g. `smtp+tls://USER:PASSWORD@smtp.example.com:587`. Required: production refuses to start without it |
| `DEFAULT_FROM_EMAIL` | e.g. `StatsTricks360 <no-reply@DOMAIN>`, on a domain the provider may send for (SPF and DKIM set) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | the OAuth client, with `https://DOMAIN/accounts/google/login/callback/` as its redirect. Google sign-in is shown only when both are set |
| `ADMIN_OTP_REQUIRED` | leave unset: production requires a TOTP code for the admin |

`DEBUG` is off in production whatever the environment says.

## Each deploy (the release step)

Run in this order, from the code's folder, with the variables above:

```bash
python manage.py migrate --noinput
python manage.py import_site          # the pages, courses, units, syllabus items, and the site's files
python manage.py import_questions     # the question bank, papers and their links to units
python manage.py collectstatic --noinput
python manage.py check --deploy
```

- **Both imports can be run again safely.** They update what changed and leave learners' progress and
  attempts alone; `import_questions` records each question's change in its history. `--dry-run`
  shows what either would do.
- **`import_site` also writes the site's own files** (images, scripts, style sheets) to
  `SITE_ROOT_DIR` (`var/site_root`), which WhiteNoise serves at their old paths. On a platform whose
  disk is rebuilt at each deploy, it must run in the release step or the build, not once by hand.
- **MathJax is served by the app** (`static/vendor/mathjax`, version 3.2.2). The pages need no CDN
  for formulas.
- **The first deploy** also needs the owner's account:
  1. `python manage.py createsuperuser`;
  2. sign in to `/staff/` and set up TOTP;
  3. add the owner, and the second reviewer, to the "Reviewers" group.

## The nightly job

Once a day, at a quiet hour (for India, 02:30 IST is 21:00 UTC):

```
0 21 * * *   cd /app && python manage.py item_stats
```

- It works out p and r_pb for every question with 30 or more responses, flags those that look wrong,
  and sends the reviewers one email when it flags any (`docs/PHASE-6-REPORT.md`).
- It needs the same environment variables as the web process, the email ones included.
- It is safe to run twice: a question already flagged, or approved since, is not flagged again on the
  same evidence.

## Backups

- **The managed database's own daily backups, kept 30 days.** Point-in-time recovery, if the plan
  offers it.
- **A restore test before launch, and then monthly:**
  1. restore the latest backup into a new, separate database;
  2. run `python manage.py data_counts` against it (with `DATABASE_URL` pointing there), and against
     production;
  3. the figures agree, or differ only by what happened since the backup;
  4. note the date and the result, then delete the copy.
- **By hand, before a risky change:**
  - back up: `pg_dump -Fc -f nrstatlab-YYYY-MM-DD.dump "$DATABASE_URL"`;
  - restore: `pg_restore --clean --if-exists -d "$DATABASE_URL" nrstatlab-YYYY-MM-DD.dump`.

  Check 7.2 in `docs/LOCAL-CHECK.md` rehearses this offline.
- **A backup holds learners' personal data** (emails, names, answers). Keep it where the database is
  kept, never in the repository (`backups/` is ignored by git), and delete copies when they are done
  with.

## Security, as built (Phase 7, the offline part)

- **HTTPS only:** HSTS, and secure, HTTP-only cookies. `check --deploy` is clean.
- **A Content Security Policy on every response** (`apps/core/csp.py`):
  - the application's pages allow scripts from this origin only;
  - each page of the site also allows exactly what it runs, read from its own HTML: the hash of each
    inline script, its inline handlers by hash, and the outside libraries four lab and notes pages
    load (Mermaid, Prism, jQuery, Google Fonts);
  - no page may be framed, and forms post only to this origin (and Google, for sign-in).
- **Logs** go to the console, where the platform collects them. Request bodies are never logged.
- **Sign-in:** five wrong passwords for an account from one address lock it for an hour. The admin
  needs TOTP.
- **Authorisation:** every route that takes an id is listed in `tests/test_authorisation.py`, with how
  it is protected. A new one fails the test until it is added.
- **Dependencies:** CI runs `pip-audit -r requirements.txt` on every push.

## Decisions still open (the owner's)

1. **The host.** Any managed platform with PostgreSQL 16, daily backups and a scheduler. Once it is
   chosen, set django-axes to read the client's address from the platform's proxy header
   (`AXES_IPWARE_PROXY_COUNT` and `AXES_IPWARE_META_PRECEDENCE_ORDER`), so that the lockout counts
   per learner, not per proxy.
2. **The domain.** Then `ALLOWED_HOSTS`, `SITE_ORIGIN`, and HTTPS.
3. **The email provider.** Then `EMAIL_URL`, `DEFAULT_FROM_EMAIL`, and SPF and DKIM on the domain.
4. **Google sign-in.** An OAuth client in Google Cloud, with the domain's callback.
5. **The legal review** of the privacy notice (`/privacy.html`), before real learners sign up.
6. **Staging, then going live:** the release step above on a staging address, `docs/LOCAL-CHECK.md`
   walked there too, a restore test, and only then the live domain and a link from the current site.
