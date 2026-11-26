from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Category,
    Subject,
    SyllabusVersion,
    Topic,
    Subtopic,
    Question,
    ExamYear,
    StudentProfile,
    PracticeAttempt,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(SyllabusVersion)
class SyllabusVersionAdmin(admin.ModelAdmin):
    list_display = ("subject", "year")
    list_filter = ("year",)
    search_fields = ("subject__name",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "syllabus_version")
    list_filter = ("syllabus_version",)
    search_fields = ("name",)


@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ("name", "topic")
    list_filter = ("topic",)
    search_fields = ("name",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):

    @admin.display(description="Question")
    def question_preview(self, obj):
        if len(obj.text) > 90:
            return f"{obj.text[:90]}..."
        return obj.text

    list_display = (
        "question_preview",
        "subtopic",
        "source_type",
        "source_year",
        "difficulty",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "source_type",
        "source_year",
        "difficulty",
        "subtopic__topic__syllabus_version__subject",
    )

    search_fields = (
        "text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "subtopic__name",
        "subtopic__topic__name",
    )

    autocomplete_fields = ("subtopic",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "subtopic__topic__syllabus_version__subject",
    )

    ordering = ("status", "-created_at")
    list_per_page = 50
    save_on_top = True

    actions = (
        "publish_questions",
        "return_to_draft",
        "archive_questions",
    )

    fieldsets = (
        (
            "Question",
            {
                "fields": (
                    "subtopic",
                    "text",
                    "option_a",
                    "option_b",
                    "option_c",
                    "option_d",
                    "correct_option",
                    "explanation",
                )
            },
        ),
        (
            "Classification",
            {
                "fields": (
                    "difficulty",
                    "source_type",
                    "source_year",
                    "status",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.action(description="Publish selected questions")
    def publish_questions(self, request, queryset):
        published_count = 0
        failed_count = 0

        for question in queryset.iterator():
            try:
                question.full_clean()

                question.status = "published"
                question.save()

                published_count += 1

            except ValidationError:
                failed_count += 1

        if published_count:
            self.message_user(
                request,
                f"{published_count} question(s) published successfully.",
                messages.SUCCESS,
            )

        if failed_count:
            self.message_user(
                request,
                f"{failed_count} question(s) could not be published. "
                "Their status was not changed. Review their details.",
                messages.WARNING,
            )

    @admin.action(description="Return selected questions to draft")
    def return_to_draft(self, request, queryset):
        count = queryset.update(status="draft")

        self.message_user(
            request,
            f"{count} question(s) returned to draft.",
            messages.SUCCESS,
        )

    @admin.action(description="Archive selected questions")
    def archive_questions(self, request, queryset):
        count = queryset.update(status="archived")

        self.message_user(
            request,
            f"{count} question(s) archived successfully.",
            messages.SUCCESS,
        )


@admin.register(ExamYear)
class ExamYearAdmin(admin.ModelAdmin):
    list_display = ("year",)
    ordering = ("-year",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "exam_year")
    list_filter = ("exam_year",)
    search_fields = ("user__username",)


@admin.register(PracticeAttempt)
class PracticeAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "subtopic",
        "score",
        "total_questions",
        "started_at",
        "submitted_at",
    )

    list_filter = (
        "subtopic",
        "submitted_at",
    )

    search_fields = (
        "student__user__username",
        "subtopic__name",
    )

    readonly_fields = (
        "student",
        "subtopic",
        "started_at",
        "submitted_at",
        "score",
        "total_questions",
    )