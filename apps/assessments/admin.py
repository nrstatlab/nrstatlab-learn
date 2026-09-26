from django.contrib import admin

from .models import Attempt, Choice, ItemStats, Question, QuestionUnit, Response, UnitTest


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionUnitInline(admin.TabularInline):
    model = QuestionUnit
    extra = 0
    raw_id_fields = ["unit"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["uid", "qtype", "status", "source"]
    list_filter = ["status", "qtype", "source"]
    search_fields = ["uid", "stem_html"]
    inlines = [ChoiceInline, QuestionUnitInline]


@admin.register(UnitTest)
class UnitTestAdmin(admin.ModelAdmin):
    list_display = ["unit", "n_questions", "pass_mark"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "user", "started_at", "submitted_at", "score"]
    list_filter = ["kind"]


admin.site.register(Response)
admin.site.register(ItemStats)
