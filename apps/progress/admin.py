from django.contrib import admin

from .models import ActivityEvent, UnitProgress


@admin.register(UnitProgress)
class UnitProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "unit", "status", "studied_at", "passed_at", "source"]
    list_filter = ["status", "source"]


admin.site.register(ActivityEvent)
