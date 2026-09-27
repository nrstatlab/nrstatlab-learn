# Checking NRSTATLAB Learn on your own computer

The application is being built and checked **offline only**. Nothing of it is online:
- the live site on GitHub Pages is unchanged;
- there is no hosting, no staging address and no domain;
- nothing will be, until you have ticked every check below and signed off.

This page shows you how to run the whole platform on your own computer and try every feature built
so far. From Phase 4 on, each phase adds its own section, so that the final sign-off is this list,
all ticked.

## 1. Start it

**Once:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
[git](https://git-scm.com/downloads), and start Docker Desktop.

**Get the code** (in a terminal):

```bash
git clone --recurse-submodules https://github.com/nrstatlab/nrstatlab-learn.git
cd nrstatlab-learn
```

**Start:**

```bash
docker compose up --build
```

- **The first start takes a few minutes.** It builds the app, then prepares the database: all 693
  pages of the site, the 950 questions and three demo accounts.
- **When the window shows `Ready. Open http://localhost:8000`,** open
  **http://localhost:8000** in your browser.
- **Keep that window open.** It is also where emails appear (below).

**The demo accounts.** The password for all three is `local-check-only`.

| Account | What it is for |
|---|---|
| `owner@localhost` | You, as staff: the admin at http://localhost:8000/staff/ |
| `new.learner@localhost` (Meera) | A learner who has done nothing yet |
| `progress.learner@localhost` (Arjun) | A learner with progress: Descriptive Statistics Unit 3 studied and its test failed (30%); UGC NET Unit 7 studied and its test passed (100%) |

**Emails.** Sign-up and password reset emails are not sent anywhere. They are printed in the window
where `docker compose up` runs. If you started it with `-d`, run `docker compose logs web` to see
them.

**Stop:** press Ctrl+C in that window, or run `docker compose down`.

**Start again from nothing:** `docker compose down -v`, then `docker compose up --build`.

**Get the latest version later:**

```bash
git pull --recurse-submodules
docker compose up --build
```

**Needs internet for one thing:** the mathematics on the pages is drawn by MathJax, loaded from the
internet, exactly as on the live site today. Without a connection, formulas show as `$…$` text.
Everything else works offline.

## 2. The checks

Tick each box when it does what it says. If one doesn't, note its number and what happened, and tell
me in the chat, or open an issue on the repository.

A tip: use a private (incognito) window as a second browser, or as a second learner.

### Phase 1: the site, served by the app

- [ ] **1.1** http://localhost:8000 shows the NRSTATLAB home page, as on the live site.
- [ ] **1.2** Open a unit from the menu, for example Statistics → Descriptive Statistics → Unit 3.
  The page, its sections and its maths look as on the live site.
- [ ] **1.3** The search box (the magnifier in the bar) finds a topic, say "median", and its
  results open.
- [ ] **1.4** An old address still works:
  http://localhost:8000/statistics/bsc/sampling-techniques/unit2.html moves to
  `/statistics/sampling-techniques/unit2.html`.
- [ ] **1.5** A missing page, http://localhost:8000/no/such/page.html, shows the site's own "page not
  found" page.

### Phase 2: accounts and progress

- [ ] **2.1 Sign-up needs all three things.** Click **Sign in**, then **sign up**. Sign-up refuses
  to go ahead without a name, "I am 18 or over" and "I have read the privacy notice".
- [ ] **2.2 The email must be confirmed.** Sign up with any address, for example
  `you@localhost`. The window shows an email with a link. Open the link, confirm, and you are
  signed in on your dashboard.
- [ ] **2.3 Mark a unit done.** Signed out (use a private window), open a unit and press **Mark this
  unit done**. It turns green: saved in this browser only.
- [ ] **2.4 Bring over your earlier progress.** In the same window, sign in as
  `new.learner@localhost`. A banner offers to bring over the page you marked. Press **Bring over**:
  the unit is now saved to the account. Signing in again does not ask a second time.
- [ ] **2.5 The same progress on another device.** In a different browser, or another private
  window, sign in as the same learner. The unit shows as done there too. Press "undo" there, then
  reload in the first browser: it is undone there as well.
- [ ] **2.6 The dashboard** (**My progress** in the bar) shows:
  - the greeting;
  - "Continue where you left off";
  - the course with a progress bar;
  - the day streak.
- [ ] **2.7 Signing out gives the browser back.** Sign out: the unit ticks you had as a guest before
  signing in come back, and the learner's do not show.
- [ ] **2.8 Download my data** (dashboard) gives a file holding your account, your progress and your
  tests, and nobody else's.
- [ ] **2.9 The privacy page** (the "Privacy" link at the foot of the app's pages) says, in plain
  words:
  - what is kept;
  - that there are no ads or trackers;
  - how to download or delete.
- [ ] **2.10 Delete my account.** Use the account you made in 2.2 (not a demo one). It asks for the
  password. After deleting, you are signed out, a confirmation email appears in the window, and that
  account can no longer sign in.

### Phase 3: unit tests

- [ ] **3.1 A guest is told about the test.** Signed out, open UGC NET Unit 7
  (http://localhost:8000/exams/ugc-net/unit7.html) and scroll to the end. A box says "Unit test: 10
  questions, pass at 70%", with **Sign in** to take it.
- [ ] **3.2 Locked until the unit is done.** Sign in as `new.learner@localhost` and open the same
  unit. The box says the test opens when you mark the unit done. Press **Mark this unit done**: the
  box now offers **Take the test**.
- [ ] **3.3 Take a test.** Start it and choose answers: each one shows "Saved". Submitting with some
  unanswered asks you to confirm first.
- [ ] **3.4 The result** shows the score and whether it is a pass, then every question with your
  answer, the correct answer and the working, and links back to the unit.
- [ ] **3.5 Take it again.** **Take the test again** gives mostly new questions; the ones you have
  not seen come first.
- [ ] **3.6 A pass shows everywhere.** Sign in as `progress.learner@localhost`:
  - UGC NET Unit 7 shows "Passed, best 100%" in its box;
  - the dashboard lists the last tests;
  - "undo" on that unit does not un-pass it.
- [ ] **3.7 A unit without enough questions has no test.** Descriptive Statistics Unit 5
  (http://localhost:8000/statistics/descriptive-statistics/unit5.html) has no test box.
- [ ] **3.8 Flagged questions are never asked.** In the admin (http://localhost:8000/staff/, as
  `owner@localhost`), open **Questions** and filter by status **flagged**. You see 37 questions,
  each with its reason. They are the ones whose key is in doubt, and none of them appears in any
  test.
- [ ] **3.9 You decide.** Open one of those questions, change its status to **published**, and save.
  It can now be drawn in its unit's test.

  For example, UGC NET Unit 5 Q50, once you have settled its key. The solved-paper flags are listed
  in `docs/PHASE-3-REPORT.md`, "For the owner", sorted into printing-only and arguable keys.
- [ ] **3.10 In the dark.** With your computer set to dark mode, the test and result pages are
  readable.
- [ ] **3.11 On a phone-sized window.** Narrow the browser window to about the width of a phone. The
  bar, a unit page with its test box, and a test all fit without scrolling sideways.

### Last of all

- [ ] **L.1 Five wrong passwords lock sign-in.** Do this one last: it locks the account for a while.
  Sign in as `new.learner@localhost` with a wrong password five times. The sixth try is refused even
  with the right password. To clear it at once:
  1. run `docker compose exec web python manage.py axes_reset`;
  2. restart: Ctrl+C, then `docker compose up`.

  Otherwise it clears by itself within an hour.

## 3. What is not here yet

- **Phase 4, old papers:** practice and exam mode for the three solved papers.
- **Phase 5:** readiness for your exam.
- **Phase 6:** the quality loop, item statistics and review.
- **Phase 7:** launch: security, hosting and the domain.
- **Google sign-in** appears once its client is set up, before staging.

## 4. Without Docker

With Python 3.12 and PostgreSQL 16 installed, follow "Run it locally" in `README.md`, then run:

```bash
python manage.py setup_local      # the database, the content, the questions and the demo accounts
python manage.py runserver
```
