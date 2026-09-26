from django.db import models


class Redirect(models.Model):
    """An old URL of the static site (a redirect stub) and where it now lives."""

    old_path = models.CharField(max_length=300, unique=True)
    new_path = models.CharField(max_length=300)

    def __str__(self):
        return f"{self.old_path} -> {self.new_path}"
