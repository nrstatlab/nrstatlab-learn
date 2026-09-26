from django.contrib import admin

from .models import Exam, ExamPaper, ExamTarget, SyllabusItem, SyllabusLink


class SyllabusLinkInline(admin.TabularInline):
    model = SyllabusLink
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "conducting_body", "order"]


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ["exam", "code", "title"]


@admin.register(SyllabusItem)
class SyllabusItemAdmin(admin.ModelAdmin):
    list_display = ["exam", "code", "grade", "text"]
    list_filter = ["exam", "grade"]
    inlines = [SyllabusLinkInline]


admin.site.register(ExamTarget)
