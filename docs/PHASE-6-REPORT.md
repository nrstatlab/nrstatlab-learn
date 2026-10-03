# Phase 6 report: The quality loop

**Status:** done; approved by the owner on 3 October 2026. **Date:** 29 September 2026.

Everything here runs on a computer only. Nothing is online until the owner signs off
`docs/LOCAL-CHECK.md`, which now has a Phase 6 section (checks 6.1–6.8).

## Done when (BUILD-GUIDE Step 13)

| Criterion | Result |
|---|---|
| Fixture data produces the expected p and r_pb to 3 decimals | **Met.** 40 sittings built to a pattern worked out by hand (below) give **p = 0.500** and **r_pb = 0.816**, through the command's own path from stored responses |
| A question with a negative r_pb is flagged automatically | **Met.** The same sittings with the groups swapped give **r_pb = −0.816**. The question is flagged with the reason, it leaves every test, its history records it, and the reviewers get one email |
| The reviewer workflow | **Met.** A queue of draft and flagged questions. A side-by-side review page with MathJax: the question as the learner sees it; the key, the working, the recompute log, the statistics and the unit. **Approve**, refused to the question's author. **Send back**, which needs a note. The full history |
| Every change is kept in history | **Met.** A small audit table, with no new dependency. It records imports, changes in the source, retirement, flags by the statistics, approvals, send-backs, and every edit made in the admin |
| CI | **Green on GitHub.** Run #14 on `15f6cd1` passed every step: lint, checks (the new migrations included), both import dry runs, and the full test suite with the browser tests |

## The statistics, as built

`python manage.py item_stats` is the nightly job. It processes each question with **30 or more
responses**:

```
p    = correct / n
R    = the sitting's rest-score: the share of its other counted answers that are right
M1, M0 = the mean R of those who answered the question right, and wrong
s    = the standard deviation of R, with n in the denominator
r_pb = (M1 − M0) / s × √(p (1 − p))
```

**Your two decisions:**
- **Which sittings count:** unit tests and old papers sat in exam mode. Practice is left out, since
  answers can be revealed there.
- **R is a share**, so a ten-question unit test and a 150-question paper sit on the same scale.

**What counts as a response:**
- an answer marked right or wrong;
- a blank is not a response;
- an answer to a question that did not count in that sitting (withdrawn, or its key in doubt) is left
  out;
- a sitting with fewer than two counted answers has no rest-score.

**Flagging:**
- a published question is flagged when r_pb < 0, p > 0.95 or p < 0.10;
- r_pb is "not defined" when everyone got the question right, when everyone got it wrong, or when
  s = 0;
- the reviewers (the "Reviewers" group) get one email per run, listing the flagged questions;
- **no flip-flopping:** a question a reviewer approves after a flag is flagged again only on 30 more
  responses.

**The done-when fixture, by hand.** 40 sittings of ten other questions each.
- The question is right in 20 sittings. Their rest-scores are all 0.8.
- It is wrong in 20: ten at 0.2 and ten at 0.6.
- p = 0.500, M1 = 0.8, M0 = 0.4, and the mean R is 0.6.
- s² = (20 × 0.2² + 10 × 0.4²) / 40 = 0.06, so s = 0.24495.
- r_pb = 0.4 / 0.24495 × 0.5 = **0.816**.

**Scheduling.** The command is written; running it each night belongs to the hosting (Phase 7), as a
cron entry on the managed platform. No scheduler library was added. Offline, it is run by hand
(check 6.1).

## The reviewer workflow, as built (the admin at `/staff/`)

- **Questions in the review queue:**
  - draft and flagged questions only, each with why it is there and its n, p and r_pb;
  - filtered by status (flagged, draft) and by source;
  - only reviewers see the queue: members of "Reviewers", or the owner as administrator.
- **The review page:**
  - left: the question as the learner sees it, maths drawn by MathJax;
  - right: the key and the working, the recompute log, the item statistics and the unit it is
    taught in;
  - below: its history.
- **Approve and publish:**
  - sets it published, records the reviewer and the time, and clears the flag (the old reason is kept
    in the history);
  - refused, with the button turned off, when the reviewer wrote the question (decision 8);
  - refused for a question with no key (the Commission's three withdrawn questions), which would
    otherwise be drawn into a unit test with no right answer.
- **Send back:**
  - needs a note, and returns the question to draft;
  - the queue shows "Sent back:" with the note.
- **Publishing only through the queue:**
  - the plain Questions page no longer lets anyone publish by changing the status;
  - it points to the queue, so the two-person rule cannot be stepped around;
  - flagging, drafting or retiring there still works, and is recorded.

## Checks run

| Check | Result |
|---|---|
| pytest | **209 passed**, coverage 95%. Item statistics and review 23, setup_local 6 (1 new), and the 185 from before |
| Mutation checks | **12 of 12 caught** (below) |
| The offline checklist, walked in Chromium against a fresh `docker compose` stack | **53 of 53 pass**: Phases 1–5 (3.9 now approves through the queue), the eight new Phase 6 checks, and the lockout last |
| `ruff check`, `manage.py check`, migrations check, both import dry runs | clean |
| `git -C content status` | empty |

| Broken on purpose | Caught by |
|---|---|
| The question left in its own rest-score | `test_the_fixture_gives_p_and_r_pb_to_three_decimals` |
| s with n − 1 in the denominator | the same |
| Fewer than 30 responses analysed | `test_fewer_than_thirty_responses_are_not_analysed` |
| Practice sittings counted | `test_practice_and_unsubmitted_sittings_do_not_count_but_exams_do` |
| A negative r_pb not flagged | `test_a_negative_r_pb_is_flagged_automatically_and_the_reviewers_are_told` |
| p above 0.95 not flagged | `test_the_three_reasons_to_flag` |
| A reviewer's approval not respected | `test_an_approved_question_is_flagged_again_only_on_thirty_more_responses` |
| The author may approve | `test_no_one_approves_their_own_question` |
| Sending back without a note | `test_send_back_needs_a_note` |
| Any staff member counted as a reviewer | `test_no_one_approves_their_own_question` |
| Publishing by editing the status | `test_publishing_by_editing_the_status_is_refused` |
| A question without a key approved | `test_a_question_without_a_key_cannot_be_published` |

## Found and fixed during the phase

- **A withdrawn question could have been approved.** The three questions the Commission withdrew are
  flagged and have no key. Approving one would have put a question with no right answer into a unit
  test. Approve now refuses a question without a key.

- **Learners saw raw entities in "not counted" reasons.**
  - 14 APPSC reasons, taken from the solved pages' notes, kept `&mdash;` and `&ldquo;` after their tags
    were stripped. They were shown as text on the paper review, the practice page and the unit-test
    result.
  - They are now stored as text. The re-import recorded each change in the questions' history.
- **Where the offline email appears.** The console email backend prints in the terminal where the
  command runs, not in the server's window. The command now prints its summary first and the email
  after it, and check 6.1 says so.

## Changes from the plan (recorded in ARCHITECTURE §17)

- **History is a small audit table** (`QuestionEvent`), not `django-simple-history`. It needs no new
  dependency and records what the workflow needs: who, when, the action, the status before and after,
  a note, and the fields changed.
- **No scheduler was added.** `item_stats` is scheduled by the hosting in Phase 7.
- **"Reviewed and published"** is one step: the status becomes published, and `reviewer` and
  `reviewed_at` record the review.
- **`ItemStats.cleared_at_n`** was added, so an approved question is not flagged again every night on
  the same evidence.
- **The demo data** (`setup_local`):
  - a second reviewer, `reviewer@localhost`, who is staff but not an administrator;
  - a draft question written by the owner, for the two-person rule;
  - 40 anonymous sittings of the UGC NET Unit I test, with one question planted to run backwards
    (r_pb = −0.888).

  The sittings belong to no account, as a deleted learner's would.

## Screenshots (`docs/phase6/`)

| Page | Files |
|---|---|
| The review queue | `queue-1280.png`, `queue-1280-dark.png`, `queue-390.png` |
| The review page of the planted question | `review-1280.png`, `review-1280-dark.png`, `review-390.png` |
| Your own question: Approve turned off | `own-question-1280.png`, `own-question-1280-dark.png`, `own-question-390.png` |

## For the owner

1. **Name the second reviewer** (decision 8). They need a staff account, TOTP, and membership of
   "Reviewers". Until then only you can review, and you cannot approve a question you wrote.
2. **37 questions wait in the queue:**
   - the six contested UGC NET keys;
   - the 28 solved-page notes;
   - the three withdrawn questions, which stay out, as they have no key.

   `docs/PHASE-3-REPORT.md`, "For the owner", sorts the notes into printing-only and arguable keys.
   Each can now be approved or sent back with a note, and the decision is kept.
3. **The statistics need learners.** On the live platform, a question gets figures after 30 answers.
   With ten questions per unit test, that is about 30 sittings of a unit's test, or fewer where the
   pool is small.

## Next

Phase 7 (launch: security, hosting and the domain) waits for approval. The platform stays offline
until you sign off `docs/LOCAL-CHECK.md`.
