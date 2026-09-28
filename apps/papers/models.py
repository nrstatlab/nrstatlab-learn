from django.db import models


class SolvedPaper(models.Model):
    """An old question paper, solved on the site. The timing and marking fields are
    filled only from the paper's own header, with the source recorded beside them."""

    exam = models.ForeignKey("examinations.Exam", on_delete=models.CASCADE, related_name="solved_papers")
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    held_on = models.DateField(null=True, blank=True)
    page_path = models.CharField(max_length=300, help_text="The solved page, e.g. exams/appsc/solved-2025-paper-ii.html")
    source = models.CharField(max_length=300)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_source = models.CharField(max_length=300, blank=True)
    marking_scheme = models.JSONField(null=True, blank=True)
    marking_source = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return self.title


class PaperQuestion(models.Model):
    paper = models.ForeignKey(SolvedPaper, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveSmallIntegerField()
    question = models.ForeignKey("assessments.Question", on_delete=models.PROTECT, related_name="paper_uses")
    official_key = models.CharField(max_length=20, blank=True)
    withdrawn = models.BooleanField(default=False)
    withdrawn_note = models.TextField(blank=True)
    section = models.CharField(max_length=80, blank=True, help_text="For the review's totals, e.g. Statistics")

    class Meta:
        ordering = ["paper", "number"]
        constraints = [models.UniqueConstraint(fields=["paper", "number"], name="uniq_paper_number")]


class PaperAttempt(models.Model):
    """A sitting of an old paper: in exam mode against the paper's own clock (when it
    records one), or in practice, one question at a time."""

    attempt = models.OneToOneField("assessments.Attempt", on_delete=models.CASCADE, related_name="paper_attempt")
    paper = models.ForeignKey(SolvedPaper, on_delete=models.CASCADE, related_name="attempts")
    deadline = models.DateTimeField(null=True, blank=True, help_text="Exam mode, when the paper records a duration")
    position = models.PositiveSmallIntegerField(default=1, help_text="Practice mode: the question on screen")
    revealed = models.JSONField(default=list, blank=True, help_text="Practice mode: questions whose solution was shown")
    # Decided when the paper is submitted: {number: reason} for each question that did not count.
    not_counted = models.JSONField(default=dict, blank=True)
