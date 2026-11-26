from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="unique_category_name"
            )
        ]

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=100)

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subjects"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_subject_per_category"
            )
        ]

    def __str__(self):
        return self.name


class SyllabusVersion(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="syllabus_versions"
    )

    year = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "year"],
                name="unique_syllabus_year_per_subject"
            )
        ]
        ordering = ["-year"]

    def __str__(self):
        return f"{self.subject.name} — {self.year} Syllabus"


class Topic(models.Model):
    syllabus_version = models.ForeignKey(
        SyllabusVersion,
        on_delete=models.CASCADE,
        related_name="topics"
    )

    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["syllabus_version", "name"],
                name="unique_topic_per_syllabus"
            )
        ]

    def __str__(self):
        return self.name


class Subtopic(models.Model):
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="subtopics"
    )

    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "name"],
                name="unique_subtopic_per_topic"
            )
        ]

    def __str__(self):
        return self.name


class Question(models.Model):
    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.PROTECT,
        related_name="questions"
    )

    text = models.TextField()

    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)

    CORRECT_OPTION_CHOICES = [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
    ]

    correct_option = models.CharField(
        max_length=1,
        choices=CORRECT_OPTION_CHOICES
    )

    explanation = models.TextField(blank=True)

    DIFFICULTY_CHOICES = [
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default="medium"
    )

    SOURCE_TYPE_CHOICES = [
        ("past_question", "Past Question"),
        ("model_question", "Model Question"),
    ]

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="model_question"
    )

    source_year = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        errors = {}

        if not self.text or not self.text.strip():
            errors["text"] = "Question text cannot be empty."

        options = {
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
        }

        for field, value in options.items():
            if not value or not value.strip():
                errors[field] = (
                    "All four answer options are required."
                )

        if self.source_type == "past_question":
            if not self.source_year:
                errors["source_year"] = (
                    "Past questions must have a source year."
                )
            elif self.source_year < 1900:
                errors["source_year"] = (
                    "Source year must be 1900 or later."
                )

        elif (
            self.source_type == "model_question"
            and self.source_year is not None
        ):
            errors["source_year"] = (
                "Model questions cannot have a source year."
            )

        if self.status == "published":
            if not self.explanation or not self.explanation.strip():
                errors["explanation"] = (
                    "Published questions must have an explanation."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.text[:80]


class ExamYear(models.Model):
    year = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ["-year"]

    def __str__(self):
        return str(self.year)


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )

    exam_year = models.ForeignKey(
        ExamYear,
        on_delete=models.PROTECT,
        related_name="students",
        null=True,
        blank=True,
    )

    def __str__(self):
        if self.exam_year:
            return (
                f"{self.user.username} — "
                f"JAMB {self.exam_year.year}"
            )

        return f"{self.user.username} — No exam year selected"


class PracticeAttempt(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="practice_attempts",
    )

    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.PROTECT,
        related_name="practice_attempts",
    )

    started_at = models.DateTimeField(auto_now_add=True)

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    score = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    total_questions = models.PositiveIntegerField()

    def __str__(self):
        return (
            f"{self.student.user.username} - "
            f"{self.subtopic.name}"
        )


class PracticeSession(models.Model):
    MODE_CHOICES = [
        ("practice", "Practice"),
        ("normal_exam", "Normal Exam"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("all", "All Questions"),
        ("past_question", "Past Questions"),
        ("model_question", "Model Questions"),
    ]

    ORDER_CHOICES = [
        ("sequential", "Sequential"),
        ("random", "Random"),
    ]

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("submitted", "Submitted"),
        ("abandoned", "Abandoned"),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="practice_sessions",
    )

    exam_year = models.ForeignKey(
        ExamYear,
        on_delete=models.PROTECT,
        related_name="practice_sessions",
        null=True,
        blank=True,
    )

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default="practice",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="practice_sessions",
    )

    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="practice_sessions",
    )

    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="practice_sessions",
    )

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="all",
    )

    source_year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    difficulty = models.CharField(
        max_length=10,
        choices=Question.DIFFICULTY_CHOICES,
        null=True,
        blank=True,
    )

    question_count = models.PositiveIntegerField()

    order_mode = models.CharField(
        max_length=20,
        choices=ORDER_CHOICES,
        default="random",
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="in_progress",
    )

    started_at = models.DateTimeField(auto_now_add=True)

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    score = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"{self.student.user.username} - "
            f"{self.mode} - "
            f"{self.started_at:%Y-%m-%d %H:%M}"
        )


class PracticeSessionQuestion(models.Model):
    session = models.ForeignKey(
        PracticeSession,
        on_delete=models.CASCADE,
        related_name="session_questions",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="practice_session_questions",
    )

    position = models.PositiveIntegerField()

    selected_option = models.CharField(
        max_length=1,
        choices=Question.CORRECT_OPTION_CHOICES,
        null=True,
        blank=True,
    )

    answered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_correct = models.BooleanField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["position"]

        constraints = [
            models.UniqueConstraint(
                fields=["session", "question"],
                name="unique_question_per_practice_session",
            ),
            models.UniqueConstraint(
                fields=["session", "position"],
                name="unique_position_per_practice_session",
            ),
        ]

    def __str__(self):
        return (
            f"{self.session.student.user.username} - "
            f"Question {self.position + 1}"
        )