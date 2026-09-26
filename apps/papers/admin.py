from django.contrib import admin

from .models import PaperAttempt, PaperQuestion, SolvedPaper


class PaperQuestionInline(admin.TabularInline):
    model = PaperQuestion
    extra = 0
    raw_id_fields = ["question"]


@admin.register(SolvedPaper)
class SolvedPaperAdmin(admin.ModelAdmin):
    list_display = ["title", "exam", "held_on", "duration_minutes"]
    inlines = [PaperQuestionInline]


admin.site.register(PaperAttempt)
