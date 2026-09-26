from django.db import models


class Programme(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class Course(models.Model):
    """One course folder, e.g. statistics/sampling-theory."""

    path = models.CharField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    programme = models.ForeignKey(Programme, null=True, blank=True, on_delete=models.SET_NULL)
    group = models.CharField(max_length=120, blank=True)
    level = models.CharField(max_length=40, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class RenderedPage(models.Model):
    """A page of the static site as import_site stored it.

    legacy_path is the path from the site root, e.g. statistics/sampling-theory/unit2.html.
    It is the URL the page is served at and the page id progress.js already uses.
    """

    legacy_path = models.CharField(max_length=300, unique=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    head_html = models.TextField(blank=True)
    body_html = models.TextField()
    body_class = models.CharField(max_length=200, blank=True)
    has_math = models.BooleanField(default=False)
    content_hash = models.CharField(max_length=64)
    published = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.legacy_path


class Unit(RenderedPage):
    """A page a learner can mark as studied (assets/progress-index.json)."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    number = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["course__order", "order"]


class Page(RenderedPage):
    """Every other indexed page: hubs, course homes, guides, labs, exam pages."""

    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL, related_name="pages")
