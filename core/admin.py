from django.contrib import admin

from .models import (
    Category,
    Subject,
    SyllabusVersion,
    Topic,
    Subtopic,
    Question,
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
    list_display = (
        "text",
        "subtopic",
        "source_type",
        "source_year",
        "difficulty",
        "status",
    )

    list_filter = (
        "source_type",
        "source_year",
        "difficulty",
        "status",
    )

    search_fields = (
        "text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
    )

    readonly_fields = (
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