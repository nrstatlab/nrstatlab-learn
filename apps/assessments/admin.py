from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from . import review
from .models import (
    Attempt,
    Choice,
    ItemStats,
    Question,
    QuestionEvent,
    QuestionUnit,
    Response,
    ReviewQuestion,
    UnitTest,
)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionUnitInline(admin.TabularInline):
    model = QuestionUnit
    extra = 0
    raw_id_fields = ["unit"]


class QuestionEventInline(admin.TabularInline):
    """The question's history, read only."""

    model = QuestionEvent
    extra = 0
    can_delete = False
    fields = ["at", "action", "user", "from_status", "to_status", "note", "changes"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"

    def clean_status(self):
        """Publishing goes through the review queue, where the two-person rule holds."""
        status = self.cleaned_data["status"]
        was = self.instance.status if self.instance.pk else None
        if status == Question.PUBLISHED and was != Question.PUBLISHED:
            raise ValidationError("Publish a question from the review queue (Approve), where another reviewer "
                                  "checks it.")
        return status


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionForm
    list_display = ["uid", "qtype", "status", "source"]
    list_filter = ["status", "qtype", "source"]
    search_fields = ["uid", "stem_html"]
    readonly_fields = ["reviewer", "reviewed_at", "source_hash"]
    inlines = [ChoiceInline, QuestionUnitInline, QuestionEventInline]

    def save_model(self, request, obj, form, change):
        before = Question.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if change else ""
        super().save_model(request, obj, form, change)
        # the long HTML fields are noted as changed; the rest with their new value
        edited = {f: "changed" if f in ("stem_html", "solution_html") else str(form.cleaned_data.get(f))
                  for f in form.changed_data}
        if edited:
            review.record(obj, QuestionEvent.EDITED, user=request.user, from_status=before or "",
                          to_status=obj.status, changes=edited)


class QueueStatusFilter(admin.SimpleListFilter):
    title, parameter_name = "status", "status"

    def lookups(self, request, model_admin):
        return [(Question.FLAGGED, "flagged"), (Question.DRAFT, "draft")]

    def queryset(self, request, queryset):
        return queryset.filter(status=self.value()) if self.value() else queryset


@admin.register(ReviewQuestion)
class ReviewQueueAdmin(admin.ModelAdmin):
    """Draft and flagged questions, each opened as a side-by-side review page with
    Approve and Send back (BUILD-GUIDE Step 13)."""

    list_display = ["uid", "status", "why", "source", "stats_n", "stats_p", "stats_rpb"]
    list_filter = [QueueStatusFilter, "source"]
    search_fields = ["uid", "stem_html", "flag_reason"]
    list_select_related = ["stats"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(status__in=[Question.DRAFT, Question.FLAGGED])

    # Reviewers, and only reviewers, see the queue; nothing is added or deleted here.
    def has_module_permission(self, request):
        return review.is_reviewer(request.user)

    def has_view_permission(self, request, obj=None):
        return review.is_reviewer(request.user)

    def has_change_permission(self, request, obj=None):
        return review.is_reviewer(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="why it is here")
    def why(self, q):
        text = q.flag_reason or "draft"
        return text if len(text) <= 90 else text[:88] + "…"

    @admin.display(description="n")
    def stats_n(self, q):
        s = getattr(q, "stats", None)
        return s.n if s else "–"

    @admin.display(description="p")
    def stats_p(self, q):
        s = getattr(q, "stats", None)
        return f"{s.difficulty:.3f}" if s and s.difficulty is not None else "–"

    @admin.display(description="r_pb")
    def stats_rpb(self, q):
        s = getattr(q, "stats", None)
        return f"{s.point_biserial:.3f}" if s and s.point_biserial is not None else "–"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if not review.is_reviewer(request.user):
            raise PermissionDenied
        q = get_object_or_404(Question.objects.select_related("author", "reviewer"), pk=object_id)
        if request.method == "POST":
            action, note = request.POST.get("action"), request.POST.get("note", "")
            try:
                if action == "approve":
                    review.approve(q, request.user, note)
                    self.message_user(request, f"{q.uid} is approved and published.", messages.SUCCESS)
                elif action == "send_back":
                    review.send_back(q, request.user, note)
                    self.message_user(request, f"{q.uid} is sent back to draft, with your note.", messages.SUCCESS)
                else:
                    raise review.ReviewRefused("Choose Approve or Send back.")
            except review.ReviewRefused as e:
                self.message_user(request, str(e), messages.ERROR)
                return redirect(request.path)
            return redirect(reverse("admin:assessments_reviewquestion_changelist"))
        choices = list(q.choices.order_by("order"))
        context = {
            **self.admin_site.each_context(request),
            "title": f"Review {q.uid}",
            "q": q,
            "options": [c for c in choices if not c.side],
            "left": [c for c in choices if c.side == Choice.LEFT],
            "right": [c for c in choices if c.side == Choice.RIGHT],
            "key": [c.label for c in choices if c.is_correct and not c.side],
            "stats": ItemStats.objects.filter(question=q).first(),
            "units": list(q.unit_links.values_list("unit__title", "unit__legacy_path")),
            "events": review.history(q),
            "own": q.author_id is not None and q.author_id == request.user.pk,
            "opts": self.model._meta,
            "full_edit": reverse("admin:assessments_question_change", args=[q.pk]),
        }
        return TemplateResponse(request, "admin/assessments/review_question.html", context)


@admin.register(UnitTest)
class UnitTestAdmin(admin.ModelAdmin):
    list_display = ["unit", "n_questions", "pass_mark"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "user", "started_at", "submitted_at", "score"]
    list_filter = ["kind"]


@admin.register(ItemStats)
class ItemStatsAdmin(admin.ModelAdmin):
    list_display = ["question", "n", "p", "r_pb", "cleared_at_n", "updated_at"]
    search_fields = ["question__uid"]

    @admin.display(description="p")
    def p(self, s):
        return f"{s.difficulty:.3f}" if s.difficulty is not None else "–"

    @admin.display(description="r_pb")
    def r_pb(self, s):
        return f"{s.point_biserial:.3f}" if s.point_biserial is not None else "–"


admin.site.register(Response)
