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
        on_delete=models.CASCADE,
        related_name="subtopics"
    )
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name