from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

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
        unique_together = ("subject", "year")
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

    def __str__(self):
        return self.name


class Subtopic(models.Model):
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="subtopics"
    )
    name = models.CharField(max_length=100)

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
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="draft"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.text[:80]