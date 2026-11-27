from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    ExamYear,
    Question,
    StudentProfile,
    Subject,
    Subtopic,
    Topic,
)


class StudentRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = [
            "full_name",
            "username",
            "email",
            "password1",
            "password2",
        ]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if " " in username:
            raise forms.ValidationError(
                "Username cannot contain spaces."
            )

        if User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "This username is already taken."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        user.first_name = self.cleaned_data["full_name"].strip()
        user.email = self.cleaned_data["email"].strip()

        if commit:
            user.save()
            StudentProfile.objects.create(user=user)

        return user


class PracticeSelectionForm(forms.Form):
    MODE_CHOICES = [
        ("practice", "Practice Mode"),
        ("normal_exam", "Normal Exam Mode"),
    ]

    DURATION_CHOICES = [
        (15, "15 minutes"),
        (30, "30 minutes"),
        (45, "45 minutes"),
        (60, "60 minutes"),
        (90, "90 minutes"),
        (120, "120 minutes"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("all", "All Questions"),
        ("past_question", "Past Questions"),
        ("model_question", "Model Questions"),
    ]

    DIFFICULTY_CHOICES = [
        ("", "All Difficulties"),
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    ]

    ORDER_CHOICES = [
        ("sequential", "Sequential"),
        ("random", "Random"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="practice",
    )

    exam_year = forms.ModelChoiceField(
        queryset=ExamYear.objects.all(),
        required=False,
        empty_label="Choose exam year (optional)",
    )

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all().order_by("name"),
        required=False,
        empty_label="All subjects",
    )

    topic = forms.ModelChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        empty_label="All topics",
    )

    subtopic = forms.ModelChoiceField(
        queryset=Subtopic.objects.none(),
        required=False,
        empty_label="All subtopics",
    )

    source_type = forms.ChoiceField(
        choices=SOURCE_TYPE_CHOICES,
        initial="all",
    )

    source_year = forms.IntegerField(
        required=False,
        min_value=1900,
        label="Past-question year",
    )

    difficulty = forms.ChoiceField(
        choices=DIFFICULTY_CHOICES,
        required=False,
    )

    number_of_questions = forms.IntegerField(
        required=True,
        min_value=1,
        label="Number of questions",
    )

    order = forms.ChoiceField(
        choices=ORDER_CHOICES,
        initial="random",
    )

    duration_minutes = forms.TypedChoiceField(
        choices=[("", "Choose duration")] + DURATION_CHOICES,
        required=False,
        coerce=lambda value: int(value) if value else None,
        label="Exam duration",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        published_questions = Question.objects.filter(
            status="published"
        )

        self.fields["topic"].queryset = Topic.objects.filter(
            syllabus_version__subject__in=Subject.objects.all()
        ).distinct().order_by("name")

        self.fields["subtopic"].queryset = Subtopic.objects.filter(
            topic__in=self.fields["topic"].queryset
        ).distinct().order_by("name")

        if self.is_bound:
            subject_id = self.data.get("subject")
            topic_id = self.data.get("topic")

            if subject_id:
                self.fields["topic"].queryset = (
                    Topic.objects.filter(
                        syllabus_version__subject_id=subject_id
                    ).order_by("name")
                )

            if topic_id:
                self.fields["subtopic"].queryset = (
                    Subtopic.objects.filter(
                        topic_id=topic_id
                    ).order_by("name")
                )

        self.fields["subject"].queryset = (
            Subject.objects.filter(
                syllabus_versions__topics__subtopics__questions__in=(
                    published_questions
                )
            )
            .distinct()
            .order_by("name")
        )

    def clean(self):
        cleaned_data = super().clean()

        mode = cleaned_data.get("mode")
        exam_year = cleaned_data.get("exam_year")
        subject = cleaned_data.get("subject")
        topic = cleaned_data.get("topic")
        subtopic = cleaned_data.get("subtopic")
        source_type = cleaned_data.get("source_type")
        source_year = cleaned_data.get("source_year")
        duration = cleaned_data.get("duration_minutes")

        if mode == "normal_exam":
            if not subject:
                self.add_error(
                    "subject",
                    "Choose a subject for Normal Exam Mode.",
                )

            if not duration:
                self.add_error(
                    "duration_minutes",
                    "Choose a duration for Normal Exam Mode.",
                )

        if topic and subject:
            if topic.syllabus_version.subject_id != subject.id:
                self.add_error(
                    "topic",
                    "The selected topic does not belong to this subject.",
                )

        if subtopic and topic:
            if subtopic.topic_id != topic.id:
                self.add_error(
                    "subtopic",
                    "The selected subtopic does not belong to this topic.",
                )

        if subtopic and not topic:
            self.add_error(
                "subtopic",
                "Choose its topic first.",
            )

        if topic and not subject:
            self.add_error(
                "topic",
                "Choose its subject first.",
            )

        if source_type == "past_question" and not source_year:
            # A source year is optional when selecting all past-question years.
            pass

        if source_type == "model_question" and source_year:
            self.add_error(
                "source_year",
                "Model questions do not have a past-question year.",
            )

        if exam_year and not ExamYear.objects.filter(
            pk=exam_year.pk
        ).exists():
            self.add_error(
                "exam_year",
                "Select a valid exam year.",
            )

        return cleaned_data