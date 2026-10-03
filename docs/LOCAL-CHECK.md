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

- **The first start takes a few minutes.** It builds the app, then prepares the database: all 705
  pages of the site, the 1,150 questions and four demo accounts.
- **When the window shows `Ready. Open http://localhost:8000`,** open
  **http://localhost:8000** in your browser.
- **Keep that window open.** It is also where emails appear (below).

**The demo accounts.** The password for all four is `local-check-only`.

| Account | What it is for |
|---|---|
| `owner@localhost` | You, as staff and a reviewer: the admin at http://localhost:8000/staff/ |
| `reviewer@localhost` (Kavya) | A second reviewer (staff, not an administrator), for the two-person rule |
| `new.learner@localhost` (Meera) | A learner who has done nothing yet |
| `progress.learner@localhost` (Arjun) | A learner with progress: Descriptive Statistics Unit 3 studied and its test failed (30%); UGC NET Unit 7 studied and its test passed (100%); the APPSC 2025 paper sat as an exam (80.10 of 149); preparing for UGC NET |

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

**Needs internet only for the first download.** Once `docker compose up --build` has run once, the
platform works with Wi-Fi off. The mathematics is drawn by the app's own copy of MathJax, so formulas
appear offline too. The one exception is four lab and notes pages that load an outside library for
their demonstration:
- Mermaid diagrams on two Data Science units;
- Prism and Google Fonts on the archived Machine Learning notes;
- jQuery on one Web Technologies lab.

Offline, those demonstrations don't run; the rest of each page does.

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
  `owner@localhost`), open **Questions** and filter by status **flagged**: there are none, since you
  settled all 37 on 2 October 2026. Filter by **retired**: APPSC 2025 Q134 (`appsc-aso-2025-q134`) is
  there, as no option is correct, so it is never asked. Now put one in review yourself: open
  `ugc-mcq-u05-q50`, set its status to **flagged**, and save. It is now in **Questions in the review
  queue**, and it no longer appears in the UGC NET Unit 5 test.
- [ ] **3.9 You decide.** A question is published only from **Questions in the review queue** (in the
  admin, under Assessments). Open `ugc-mcq-u05-q50` there and press **Approve and publish**. It leaves
  the queue and can be drawn in its unit's test again.
- [ ] **3.10 In the dark.** With your computer set to dark mode, the test and result pages are
  readable.
- [ ] **3.11 On a phone-sized window.** Narrow the browser window to about the width of a phone. The
  bar, a unit page with its test box, and a test all fit without scrolling sideways.

### Phase 4: old papers

The three solved papers can be practised one question at a time, or sat as an exam under the paper's
own rules. Sign in as `new.learner@localhost` unless a check says otherwise.

- [ ] **4.1 The box on the solved pages.** Signed out, open the solved APPSC 2025 paper
  (http://localhost:8000/exams/appsc/solved-2025-paper-ii.html). Under the bar, a box says "Try
  this paper yourself … (150 questions, 150 minutes, −0.33 for a wrong answer)", with **Sign in to
  practise or sit it**. Signed in, the button reads **Practise or sit it**. The solved APPSC 2022 and UGC NET 2026 pages have the
  same box.
- [ ] **4.2 The rules, from the paper itself.** http://localhost:8000/papers/ lists the three papers.
  Each paper's page states:
  - the number of questions;
  - the time, and where it comes from;
  - the marking, and where it comes from;
  - the questions that do not count, and why.

  APPSC 2025: 150 minutes, +1 and −0.33, Q134 not counted as no option is correct, **149 count**.
  APPSC 2022: 150 minutes, +1 and −0.33, **all 150 count**.
- [ ] **4.3 UGC NET 2026 has no timer and no negative marks.** Its page says the paper records
  neither, so there is no clock, each question is one mark, and all 150 count.
- [ ] **4.4 Practise.** On the UGC NET 2026 page press **Practise**. Choose an answer and press
  **Check my answer**: it says right or not, shows the key and the working, and "Study this" where
  the site teaches it. On another question, **Show the solution** shows the same without
  answering.
- [ ] **4.5 Practice keeps your place.** Go on a few questions with **Next →**, then leave and come
  back to the paper's page: **Carry on practising** returns you to the same question.
- [ ] **4.6 Sit APPSC 2025 as an exam.** On its page press **Sit the paper**. The whole paper is on
  one page, in its sections, with a bar that stays in view: "N of 149 answered" and the time left,
  counting down. **Questions** opens a grid of numbers; answered ones turn solid. Reload the page:
  your answers and the clock are unchanged.
- [ ] **4.7 A question with no correct option.** Q134 is greyed, says "Not counted. No option is
  correct", with why, and has nothing to choose.
- [ ] **4.8 Submit and review.** Answer a few, then **Submit the paper** (it asks first if some are
  blank). The review shows:
  - the score out of 149, with 0.33 taken off for each wrong answer;
  - a table by section: right, wrong, blank, not counted, marks;
  - "1 question did not count" (Q134), and why;
  - every question with your answer, the right answer, the working and "Study this".

  Signed in as `progress.learner@localhost`, the review of the sitting already there reads
  **80.10 of 149.00**: 90 right, 30 wrong.
- [ ] **4.9 The dashboard** lists the papers you have sat under "Old papers", each score linking to
  its review, and a paper sat counts towards the day streak.
- [ ] **4.10 In the dark and on a phone.** In dark mode, and in a phone-sized window, the paper
  pages are readable and nothing needs scrolling sideways, except the section table, which scrolls
  within itself.

### Phase 5: readiness for your exam

Readiness is worked out from each exam's syllabus map on the site. Every line of the map is shown with
the units that teach it, and only units you have **passed** (by passing their unit test) count. Only
30 units have a test so far, so each exam also shows the most you can reach today.

- [ ] **5.1 The box on an exam's map.** Signed out, open the UGC NET map
  (http://localhost:8000/exams/ugc-net/index.html). Under the bar, a box says "How ready are you?"
  with **Sign in to see your readiness**. The maps of CSIR NET, ASRB NET, ISS (and its four paper
  pages) and APPSC (and its two post pages) have the same box.
- [ ] **5.2 The figure.** Sign in as `progress.learner@localhost`. The box on the UGC NET map now reads
  "Your readiness for UGC NET Statistics: 4.1%". **See what to study next** opens the readiness page:
  **4.1% ready**, and "12 of the 72 units this exam needs have a unit test yet, so today the most you
  can reach is **50.8%**".
- [ ] **5.3 Line by line.** Each syllabus line of the map is listed with its units, a small bar, and
  each unit's status: **passed**, **marked done** or **not started**, "in depth" or "at exam level", and
  "no test yet" where there is none. Under Unit VII: Time Series, UGC NET Unit VII shows **passed**.
- [ ] **5.4 What is not counted.** On the ISS page (http://localhost:8000/readiness/iss/), two lists at
  the end: "Taught here on pages with nothing to mark (9)" and "Not taught on this site yet (26)". The
  page says neither is in the figure.
- [ ] **5.5 Next to study.** Three units, each with the number of syllabus lines it teaches and its next
  step: "Study it, then take its test", "Take its test", or "Study it; its test is not written yet".
- [ ] **5.6 A passed test raises the figure.** Sign in as `new.learner@localhost`. CSIR NET
  (http://localhost:8000/readiness/csir-net/) reads **0% ready**. Mark UGC NET Unit II done and pass
  its test (7 of 10 or better). CSIR NET now reads **25.6% ready**: that unit alone teaches 10 of the
  39 CSIR NET lines that are counted.
- [ ] **5.7 Your exam on the dashboard.** On a readiness page press **Make this my exam**. The
  dashboard (**My progress**) shows a "Your exam" card with the figure and the next unit.
  `progress.learner@localhost` already has UGC NET as their exam. **Stop preparing for it** removes
  the card's exam.
- [ ] **5.8 In the dark and on a phone.** In dark mode and in a phone-sized window, the readiness pages
  and the box are readable and nothing needs scrolling sideways.

### Phase 6: the quality loop (approved 3 October 2026)

Each night, the live platform will work out two figures for every question with 30 or more answers,
from unit tests and exam-mode papers:
- **p**, the share who get it right;
- **r_pb**, whether those who get it right also do better on the rest of the test.

A question that looks wrong is taken out of tests and put in front of the reviewers. On this computer
you run it yourself. The demo data holds 40 anonymous sittings of the UGC NET Unit I test, with one
question planted to behave badly.

- [ ] **6.1 Run the statistics.** In a second terminal, in the `nrstatlab-learn` folder, run
  `docker compose exec web python manage.py item_stats`. It reports 10 questions with 30 or more
  responses, and 1 flagged for review: `ugc-mcq-u01-q10`, "r_pb is negative (−0.888): those who got
  it right did worse on the rest". Below that, the same terminal shows the email sent to both
  reviewers (offline, emails are printed where the command runs).
- [ ] **6.2 The review queue.** In the admin (http://localhost:8000/staff/, as `owner@localhost`),
  open **Questions in the review queue**. It lists only draft and flagged questions, with why each is
  there and its n, p and r_pb. `ugc-mcq-u01-q10` is among them with n 40, p 0.500 and r_pb −0.888.
- [ ] **6.3 Side by side.** Open it. On the left, the question as the learner sees it, maths drawn by
  MathJax. On the right:
  - the key and the working;
  - the recompute log;
  - the item statistics;
  - the unit it is taught in.

  Below, its history: imported, then flagged by statistics.
- [ ] **6.4 Approve.** Press **Approve and publish**. It leaves the queue, is published again, and
  its history now records that you approved it.
- [ ] **6.5 No one approves their own question.** Open `local-demo-draft-001`, a draft written by
  `owner@localhost`. It says "You wrote this question", and **Approve and publish** is off. Sign in to
  the admin as `reviewer@localhost` in a private window and approve it there: it is published.
- [ ] **6.6 Send back needs a note.** Put another question in review as in 3.8: in the plain
  **Questions** list open `ugc-mcq-u05-q41`, set its status to **flagged**, and save. Open it in the
  review queue and press **Send back** with the note empty: it asks for a note. Write one and send it
  back. The question becomes a draft, and the queue shows "Sent back:" with your note.
- [ ] **6.7 Approved means approved.** Run `item_stats` again. `ugc-mcq-u01-q10` is not flagged
  again: it would be only after 30 more responses.
- [ ] **6.8 Publishing only through the queue.** In the admin's plain **Questions** list, open
  `ugc-mcq-u05-q41` (the draft from 6.6), set its status to **published** and save. It is refused, and
  points you to the review queue.

### Before launch: the offline part of Phase 7 (approved 3 October 2026)

- [ ] **7.1 Formulas draw with Wi-Fi off.** Turn Wi-Fi off, or pull the network cable. Open
  http://localhost:8000/statistics/descriptive-statistics/unit3.html and scroll: every formula is
  drawn, none is left as `$…$` text. Then sign in as `progress.learner@localhost`, open
  http://localhost:8000/papers/ and click the score under the APPSC 2025 paper ("Your last
  sitting"): the review's formulas are drawn too. Turn Wi-Fi back on.
- [ ] **7.2 Back up, start again from nothing, restore.** In a second terminal, in the
  `nrstatlab-learn` folder:
  1. Sign in as `new.learner@localhost` and press **Mark this unit done** on any unit page, so
     there is something of yours to lose.
  2. See what the database holds: `docker compose exec web python manage.py data_counts`. Keep the
     output.
  3. Back up: `docker compose exec db pg_dump -U nrstatlab -Fc -f /backups/nrstatlab.dump nrstatlab`.
     The file appears in the `backups` folder on this computer.
  4. Start again from nothing: `docker compose down -v`, then `docker compose up -d`, and wait until
     http://localhost:8000 opens. Meera's unit is no longer done.
  5. Restore:
     1. `docker compose stop web`;
     2. `docker compose exec db pg_restore -U nrstatlab -d nrstatlab --clean --if-exists /backups/nrstatlab.dump`;
     3. `docker compose start web`.
  6. Run `data_counts` again. Every figure is the same as in step 2. Signed in as
     `new.learner@localhost`, that unit is done again.

### Last of all

- [ ] **L.1 Five wrong passwords lock sign-in.** Do this one last: it locks the account for a while.
  Sign in as `new.learner@localhost` with a wrong password five times. The sixth try is refused even
  with the right password. To clear it at once:
  1. run `docker compose exec web python manage.py axes_reset`;
  2. restart: Ctrl+C, then `docker compose up`.

  Otherwise it clears by itself within an hour.

## 3. What is not here yet

- **Phase 7, the online part:** the host, the domain, the email provider, the legal review, staging
  and going live. Each waits for your choice; `docs/DEPLOY.md` lists them.
- **Google sign-in** appears once its client is set up, before staging.

## 4. Without Docker

With Python 3.12 and PostgreSQL 16 installed, follow "Run it locally" in `README.md`, then run:

```bash
python manage.py setup_local      # the database, the content, the questions and the demo accounts
python manage.py runserver
```
