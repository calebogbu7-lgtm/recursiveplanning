
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from core.models import (
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
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category")
    list_filter = ("category",)
    search_fields = ("name", "category__name")
    autocomplete_fields = ("category",)
    ordering = ("name",)


@admin.register(SyllabusVersion)
class SyllabusVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "year")
    list_filter = ("year", "subject")
    search_fields = ("subject__name",)
    autocomplete_fields = ("subject",)
    ordering = ("-year",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "syllabus_version")
    list_filter = ("syllabus_version__year", "syllabus_version__subject")
    search_fields = ("name", "syllabus_version__subject__name")
    autocomplete_fields = ("syllabus_version",)
    ordering = ("name",)


@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "topic")
    list_filter = (
        "topic__syllabus_version__year",
        "topic__syllabus_version__subject",
    )
    search_fields = ("name", "topic__name")
    autocomplete_fields = ("topic",)
    ordering = ("name",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_question",
        "subtopic",
        "source_type",
        "source_year",
        "difficulty",
        "status",
        "updated_at",
    )

    list_filter = (
        "status",
        "source_type",
        "source_year",
        "difficulty",
        "subtopic__topic__syllabus_version__year",
        "subtopic__topic__syllabus_version__subject",
    )

    search_fields = (
        "text",
        "subtopic__name",
        "subtopic__topic__name",
        "subtopic__topic__syllabus_version__subject__name",
    )

    autocomplete_fields = ("subtopic",)

    readonly_fields = (
        "status",
        "created_at",
        "updated_at",
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

    actions = (
        "send_to_review",
        "publish_questions",
        "return_to_draft",
        "archive_questions",
    )

    ordering = ("-updated_at",)
    list_per_page = 25
    save_on_top = True

    @admin.display(description="Question")
    def short_question(self, obj):
        return obj.text[:80]

    @admin.action(description="Send selected draft questions for review")
    def send_to_review(self, request, queryset):
        successful = 0
        failed = 0

        for question in queryset:
            if question.status != "draft":
                continue

            question.status = "under_review"

            try:
                question.full_clean()
                question.save()
                successful += 1
            except ValidationError:
                failed += 1

        if successful:
            self.message_user(
                request,
                f"{successful} question(s) sent for review.",
                messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} question(s) could not be sent for review. "
                "Check that their required fields are complete.",
                messages.ERROR,
            )

    @admin.action(description="Publish selected questions under review")
    def publish_questions(self, request, queryset):
        successful = 0
        failed = 0

        for question in queryset:
            if question.status != "under_review":
                continue

            question.status = "published"

            try:
                question.full_clean()
                question.save()
                successful += 1
            except ValidationError:
                failed += 1

        if successful:
            self.message_user(
                request,
                f"{successful} question(s) published successfully.",
                messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} question(s) could not be published. "
                "Check that each question has a valid explanation "
                "and all required fields.",
                messages.ERROR,
            )

    @admin.action(description="Return selected archived questions to draft")
    def return_to_draft(self, request, queryset):
        updated = queryset.filter(status="archived").update(status="draft")

        self.message_user(
            request,
            f"{updated} archived question(s) returned to draft.",
            messages.SUCCESS,
        )

    @admin.action(description="Archive selected published questions")
    def archive_questions(self, request, queryset):
        updated = queryset.filter(status="published").update(
            status="archived"
        )

        self.message_user(
            request,
            f"{updated} published question(s) archived.",
            messages.SUCCESS,
        )


@admin.register(ExamYear)
class ExamYearAdmin(admin.ModelAdmin):
    list_display = ("id", "year")
    search_fields = ("year",)
    ordering = ("-year",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "exam_year")
    list_filter = ("exam_year",)
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "exam_year")


@admin.register(PracticeAttempt)
class PracticeAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "subtopic",
        "score",
        "total_questions",
        "started_at",
        "submitted_at",
    )

    list_filter = ("submitted_at",)
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

    ordering = ("-submitted_at",)
