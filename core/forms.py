from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    ExamYear,
    StudentProfile,
    Subject,
    Topic,
    Subtopic,
)


class StudentRegistrationForm(UserCreationForm):

    full_name = forms.CharField(
        max_length=150,
        label="Full Name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Ojumyi Faith",
                "autocomplete": "name",
            }
        ),
    )

    username = forms.CharField(
        max_length=150,
        label="Username",
        help_text=(
            "Use letters, numbers, @, ., +, -, or _. "
            "Spaces are not allowed."
        ),
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. ojumyifaith",
                "autocomplete": "username",
                "id": "id_username",
            }
        ),
    )

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "e.g. student@example.com",
                "autocomplete": "email",
            }
        ),
    )

    exam_year = forms.ModelChoiceField(
        queryset=ExamYear.objects.none(),
        empty_label="Select your intended JAMB exam year",
        label="JAMB Exam Year",
    )

    class Meta:
        model = User
        fields = [
            "full_name",
            "username",
            "email",
            "exam_year",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["exam_year"].queryset = ExamYear.objects.all()

        self.fields["password1"].help_text = (
            "Choose a secure password with at least 8 characters."
        )

        self.fields["password2"].help_text = (
            "Enter the same password again to confirm it."
        )

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()

        if not full_name:
            raise forms.ValidationError(
                "Please enter your full name."
            )

        return full_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if not username:
            raise forms.ValidationError(
                "Please choose a username."
            )

        if any(character.isspace() for character in username):
            raise forms.ValidationError(
                "Usernames cannot contain spaces. "
                "Try removing the space or using an underscore. "
                "For example: ojumyifaith or ojumyi_faith."
            )

        # Apply Django's normal username validation after
        # providing our own friendlier message for spaces.
        username_field = User._meta.get_field("username")

        try:
            username_field.clean(username, self)
        except ValidationError as error:
            raise forms.ValidationError(error.messages)

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists. "
                "Please log in or use another email address."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        user.first_name = self.cleaned_data["full_name"]
        user.email = self.cleaned_data["email"]

        if commit:
            user.save()

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
        help_text="Only applies when Past Questions is selected.",
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

        self.fields["subject"].queryset = (
            Subject.objects.filter(
                syllabus_versions__year=exam_year,
            )
            .distinct()
            .order_by("name")
        )

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

        if subject is not None and topic is not None:
            if topic.syllabus_version.subject_id != subject.id:
                self.add_error(
                    "topic",
                    "The selected topic does not belong "
                    "to the selected subject.",
                )

        if topic is not None and subtopic is not None:
            if subtopic.topic_id != topic.id:
                self.add_error(
                    "subtopic",
                    "The selected subtopic does not belong "
                    "to the selected topic.",
                )

        if topic is None and subtopic is not None:
            self.add_error(
                "subtopic",
                "Select a topic before selecting a subtopic.",
            )

        if source_year is not None:
            if source_type != "past_question":
                self.add_error(
                    "source_year",
                    "Past Question Year can only be used "
                    "with Past Questions.",
                )

        if source_type == "all":
            cleaned_data["source_type"] = None

        return cleaned_data