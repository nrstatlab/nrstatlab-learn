from django.contrib import admin

from .models import Course, Page, Programme, Unit


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "order"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "path", "group", "level", "order"]
    list_filter = ["group", "level"]
    search_fields = ["title", "path"]


class RenderedPageAdmin(admin.ModelAdmin):
    # Content is written in the content repository and loaded by import_site;
    # it is read-only here.
    list_display = ["legacy_path", "title", "has_math", "updated_at"]
    search_fields = ["legacy_path", "title"]
    readonly_fields = ["legacy_path", "title", "description", "head_html", "body_html", "body_class",
                       "has_math", "content_hash", "updated_at"]


@admin.register(Unit)
class UnitAdmin(RenderedPageAdmin):
    list_filter = ["course"]


@admin.register(Page)
class PageAdmin(RenderedPageAdmin):
    pass
