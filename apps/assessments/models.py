import uuid

from django.conf import settings
from django.db import models


class Question(models.Model):
    SINGLE, MULTIPLE, NUMERIC, ASSERTION, MATCH = "single", "multiple", "numeric", "assertion", "match"
    TYPES = [(SINGLE, "single choice"), (MULTIPLE, "multiple choice"), (NUMERIC, "numeric"),
             (ASSERTION, "assertion-reason"), (MATCH, "match")]
    DRAFT, REVIEWED, PUBLISHED, FLAGGED, RETIRED = "draft", "reviewed", "published", "flagged", "retired"
    STATUSES = [(DRAFT, "draft"), (REVIEWED, "reviewed"), (PUBLISHED, "published"),
                (FLAGGED, "flagged"), (RETIRED, "retired")]

    uid = models.CharField(max_length=80, unique=True, help_text="Stable id from the source, e.g. ugc-mcq-1-01")
    qtype = models.CharField(max_length=10, choices=TYPES, default=SINGLE)
    stem_html = models.TextField()
    solution_html = models.TextField(blank=True)
    # Server-only. Never passed to a template before the attempt is submitted:
    # every display goes through assessments.services.public_view().
    answer_text = models.CharField(max_length=200, blank=True)
    tolerance = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    difficulty = models.PositiveSmallIntegerField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=200)
    source_ref = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)
    flag_reason = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    recompute_log = models.TextField(blank=True)
    # A hash of what the source says (stem, choices, key, solution). An import changes
    # the status only when this changes, so a review decision made in the admin stands
    # until the question itself is edited in the source.
    source_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.uid


class Choice(models.Model):
    """An option. For a match question the rows are the two lists: side "left" (the
    items, labelled A, B, …) and side "right" (what they match, labelled I, II, …);
    the key is then Question.answer_text, a JSON object {"A": "II", …}."""

    LEFT, RIGHT = "left", "right"
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    side = models.CharField(max_length=5, blank=True, choices=[("", "option"), (LEFT, "left"), (RIGHT, "right")])
    label = models.CharField(max_length=4)
    text_html = models.TextField()
    is_correct = models.BooleanField(default=False)  # server-only, like Question.answer_text
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["question", "order"]
        constraints = [models.UniqueConstraint(fields=["question", "label"], name="uniq_choice_label")]


class QuestionUnit(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="unit_links")
    unit = models.ForeignKey("study.Unit", on_delete=models.CASCADE, related_name="question_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["question", "unit"], name="uniq_question_unit")]


class UnitTest(models.Model):
    unit = models.OneToOneField("study.Unit", on_delete=models.CASCADE, related_name="unit_test")
    n_questions = models.PositiveSmallIntegerField(default=settings.UNIT_TEST_QUESTIONS)
    pass_mark = models.PositiveSmallIntegerField(default=settings.UNIT_TEST_PASS_MARK, help_text="Percent")
    time_limit_minutes = models.PositiveSmallIntegerField(null=True, blank=True)


class Attempt(models.Model):
    """One sitting of a unit test or of an old paper (papers.PaperAttempt links the paper,
    so that this app never imports papers)."""

    UNIT_TEST, PAPER = "unit_test", "paper"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Set to NULL when the learner deletes their account: responses stay, anonymised,
    # for item statistics.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempts")
    kind = models.CharField(max_length=10, choices=[(UNIT_TEST, "unit test"), (PAPER, "paper")])
    unit_test = models.ForeignKey(UnitTest, null=True, blank=True, on_delete=models.CASCADE, related_name="attempts")
    mode = models.CharField(max_length=10, blank=True)
    seed = models.BigIntegerField()
    question_uids = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(kind="unit_test", unit_test__isnull=False)
                           | models.Q(kind="paper", unit_test__isnull=True)),
                name="attempt_kind_matches_target",
            ),
            # One open attempt per learner per unit test (BUILD-GUIDE Step 10).
            models.UniqueConstraint(fields=["user", "unit_test"], condition=models.Q(submitted_at__isnull=True),
                                    name="one_open_attempt_per_test"),
        ]


class Response(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="responses")
    answer = models.JSONField(null=True, blank=True)
    correct = models.BooleanField(null=True)
    seconds = models.PositiveIntegerField(default=0)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="uniq_response")]


class ItemStats(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name="stats")
    n = models.PositiveIntegerField(default=0)
    difficulty = models.FloatField(null=True)
    point_biserial = models.FloatField(null=True)
    updated_at = models.DateTimeField(auto_now=True)
    # The n at which a reviewer last approved this question after the statistics flagged
    # it. The nightly job flags it again only on 30 more responses (BUILD-GUIDE Step 13).
    cleared_at_n = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "item statistics"


class QuestionEvent(models.Model):
    """The history of a question: every change of status or content, who made it and
    why (BUILD-GUIDE Step 13, "every change is kept in history")."""

    IMPORTED, SOURCE_CHANGED, RETIRED = "imported", "source changed", "retired"
    STATS_FLAGGED, APPROVED, SENT_BACK, EDITED = "flagged by statistics", "approved", "sent back", "edited"
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10, blank=True)
    note = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["question", "at", "pk"]

    def __str__(self):
        return f"{self.question.uid}: {self.action}"


class ReviewQuestion(Question):
    """The reviewers' queue in the admin: draft and flagged questions."""

    class Meta:
        proxy = True
        verbose_name = "question in the review queue"
        verbose_name_plural = "questions in the review queue"
