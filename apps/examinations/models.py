from django.conf import settings
from django.db import models


class Exam(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    conducting_body = models.CharField(max_length=200, blank=True)
    official_source_url = models.URLField(blank=True)
    source_note = models.TextField(blank=True)
    hub_path = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class ExamPaper(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="papers")
    code = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["exam", "order"]
        constraints = [models.UniqueConstraint(fields=["exam", "code"], name="uniq_exam_paper")]

    def __str__(self):
        return f"{self.exam.slug} {self.code}"


class SyllabusItem(models.Model):
    DEEP, BRIEF, MISSING = "deep", "brief", "missing"
    GRADES = [(DEEP, "deep"), (BRIEF, "brief"), (MISSING, "not here")]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="items")
    paper = models.ForeignKey(ExamPaper, null=True, blank=True, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=40)
    text = models.TextField()
    grade = models.CharField(max_length=10, choices=GRADES)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["exam", "order"]
        constraints = [models.UniqueConstraint(fields=["exam", "code"], name="uniq_syllabus_code")]

    def __str__(self):
        return f"{self.exam.slug} {self.code}"


class SyllabusLink(models.Model):
    """A syllabus item's "Study this" link. unit is set when the target is a markable unit."""

    item = models.ForeignKey(SyllabusItem, on_delete=models.CASCADE, related_name="links")
    target_path = models.CharField(max_length=400)
    unit = models.ForeignKey("study.Unit", null=True, blank=True, on_delete=models.SET_NULL, related_name="syllabus_links")
    depth = models.CharField(max_length=10, choices=[("deep", "deep"), ("brief", "brief")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item", "target_path"], name="uniq_syllabus_link")]


class ExamTarget(models.Model):
    """The exam a learner is preparing for (Phase 5). Kept here, not on the profile,
    so that accounts depends on no other app."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_target")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    exam_date = models.DateField(null=True, blank=True)
