from django.conf import settings
from django.db import models


class UnitProgress(models.Model):
    NOT_STARTED, STUDYING, STUDIED, PASSED = "not_started", "studying", "studied", "passed"
    STATUSES = [(NOT_STARTED, "not started"), (STUDYING, "studying"), (STUDIED, "studied"), (PASSED, "passed")]
    RANK = {NOT_STARTED: 0, STUDYING: 1, STUDIED: 2, PASSED: 3}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="unit_progress")
    unit = models.ForeignKey("study.Unit", on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=12, choices=STATUSES, default=NOT_STARTED)
    first_seen = models.DateTimeField(auto_now_add=True)
    studied_at = models.DateTimeField(null=True, blank=True)
    passed_at = models.DateTimeField(null=True, blank=True)
    best_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=20, default="web")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "unit"], name="uniq_user_unit")]


class ActivityEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity")
    kind = models.CharField(max_length=30)
    unit = models.ForeignKey("study.Unit", null=True, blank=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(default=dict, blank=True)
