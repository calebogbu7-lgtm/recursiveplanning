from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    ExamYear,
    StudentProfile,
    Subject,
    Topic,
    Subtopic,
)


class StudentRegistrationForm(UserCreationForm):

    exam_year = forms.ModelChoiceField(
        queryset=ExamYear.objects.none(),
        empty_label="Select your JAMB exam year",
        label="JAMB Exam Year",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "exam_year",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["exam_year"].queryset = ExamYear.objects.all()

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            StudentProfile.objects.create(
                user=user,
                exam_year=self.cleaned_data["exam_year"],
            )

        return user


class PracticeSelectionForm(forms.Form):
    """
    Form used by students to define what they want to practise.

    The student's exam year is supplied by the view and is used to
    restrict the available subjects, topics, and subtopics.
    """

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        empty_label="Select a subject",
        label="Subject",
    )

    topic = forms.ModelChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        empty_label="All topics",
        label="Topic",
    )

    subtopic = forms.ModelChoiceField(
        queryset=Subtopic.objects.none(),
        required=False,
        empty_label="All subtopics",
        label="Subtopic",
    )

    SOURCE_TYPE_CHOICES = [
        ("all", "All Questions"),
        ("past_question", "Past Questions"),
        ("model_question", "Model Questions"),
    ]

    source_type = forms.ChoiceField(
        choices=SOURCE_TYPE_CHOICES,
        required=False,
        initial="all",
        label="Question Source",
    )

    source_year = forms.IntegerField(
        required=False,
        min_value=1,
        label="Past Question Year",
        help_text=(
            "Only applies when Past Questions is selected."
        ),
    )

    DIFFICULTY_CHOICES = [
        ("", "All Difficulties"),
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    difficulty = forms.ChoiceField(
        choices=DIFFICULTY_CHOICES,
        required=False,
        label="Difficulty",
    )

    number_of_questions = forms.IntegerField(
        min_value=1,
        label="Number of Questions",
        help_text=(
            "The number must not be greater than the "
            "available questions."
        ),
    )

    ORDER_CHOICES = [
        ("random", "Random"),
        ("sequential", "Sequential"),
    ]

    order = forms.ChoiceField(
        choices=ORDER_CHOICES,
        initial="random",
        label="Question Order",
    )

    def __init__(
        self,
        *args,
        exam_year=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if exam_year is None:
            return

        # -----------------------------------------------------
        # Subjects available for the student's exam year.
        # -----------------------------------------------------

        self.fields["subject"].queryset = (
            Subject.objects.filter(
                syllabus_versions__year=exam_year,
            )
            .distinct()
            .order_by("name")
        )

        # -----------------------------------------------------
        # Topics available for the student's exam year.
        # -----------------------------------------------------

        self.fields["topic"].queryset = (
            Topic.objects.filter(
                syllabus_version__year=exam_year,
            )
            .select_related(
                "syllabus_version",
                "syllabus_version__subject",
            )
            .order_by(
                "syllabus_version__subject__name",
                "name",
            )
        )

        # -----------------------------------------------------
        # Subtopics available for the student's exam year.
        # -----------------------------------------------------

        self.fields["subtopic"].queryset = (
            Subtopic.objects.filter(
                topic__syllabus_version__year=exam_year,
            )
            .select_related(
                "topic",
                "topic__syllabus_version",
                "topic__syllabus_version__subject",
            )
            .order_by(
                "topic__syllabus_version__subject__name",
                "topic__name",
                "name",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        subject = cleaned_data.get("subject")
        topic = cleaned_data.get("topic")
        subtopic = cleaned_data.get("subtopic")
        source_type = cleaned_data.get("source_type")
        source_year = cleaned_data.get("source_year")

        # -----------------------------------------------------
        # A topic must belong to the selected subject.
        # -----------------------------------------------------

        if subject is not None and topic is not None:
            if topic.syllabus_version.subject_id != subject.id:
                self.add_error(
                    "topic",
                    "The selected topic does not belong "
                    "to the selected subject.",
                )

        # -----------------------------------------------------
        # A subtopic must belong to the selected topic if a
        # topic was selected.
        # -----------------------------------------------------

        if topic is not None and subtopic is not None:
            if subtopic.topic_id != topic.id:
                self.add_error(
                    "subtopic",
                    "The selected subtopic does not belong "
                    "to the selected topic.",
                )

        # -----------------------------------------------------
        # If no topic was selected, a subtopic cannot be
        # selected because there is no topic scope.
        # -----------------------------------------------------

        if topic is None and subtopic is not None:
            self.add_error(
                "subtopic",
                "Select a topic before selecting a subtopic.",
            )

        # -----------------------------------------------------
        # Source year only makes sense for past questions.
        # -----------------------------------------------------

        if source_year is not None:
            if source_type != "past_question":
                self.add_error(
                    "source_year",
                    "Past Question Year can only be used "
                    "with Past Questions.",
                )

        # -----------------------------------------------------
        # Convert "all" into None so the selector can treat it
        # as no source restriction.
        # -----------------------------------------------------

        if source_type == "all":
            cleaned_data["source_type"] = None

        return cleaned_data