from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    ExamYear,
    Question,
    StudentProfile,
    Subject,
    Topic,
    Subtopic,
)


class StudentRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=150,
        label="Full Name",
        help_text="Enter your full name.",
    )

    username = forms.CharField(
        max_length=150,
        label="Username",
        help_text=(
            "Use letters, numbers, @, ., +, - or _. "
            "Spaces are not allowed."
        ),
    )

    email = forms.EmailField(
        required=True,
        label="Email Address",
    )

    class Meta:
        model = User
        fields = [
            "full_name",
            "username",
            "email",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
            }
        )

        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
            }
        )

        self.fields["password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
            }
        )

    def clean_username(self):
        username = self.cleaned_data["username"]

        if any(character.isspace() for character in username):
            raise forms.ValidationError(
                "Username cannot contain spaces. "
                "Please remove the spaces or use an underscore instead."
            )

        if User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "That username is already taken. "
                "Please choose another one."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
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
            )

        return user


class PracticeSelectionForm(forms.Form):

    # ---------------------------------------------------------
    # EXAM YEAR
    # ---------------------------------------------------------

    exam_year = forms.ModelChoiceField(
        queryset=ExamYear.objects.all(),
        empty_label="Select an exam year",
        label="Exam Year",
    )

    # ---------------------------------------------------------
    # SUBJECT
    # ---------------------------------------------------------

    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        empty_label="All Subjects",
        label="Subject",
    )

    # ---------------------------------------------------------
    # TOPIC
    # ---------------------------------------------------------

    topic = forms.ModelChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        empty_label="All Topics",
        label="Topic",
    )

    # ---------------------------------------------------------
    # SUBTOPIC
    # ---------------------------------------------------------

    subtopic = forms.ModelChoiceField(
        queryset=Subtopic.objects.none(),
        required=False,
        empty_label="All Subtopics",
        label="Subtopic",
    )

    # ---------------------------------------------------------
    # QUESTION SOURCE
    # ---------------------------------------------------------

    source_type = forms.ChoiceField(
        choices=[
            ("all", "All Questions"),
            ("past_question", "Past Questions"),
            ("model_question", "Model Questions"),
        ],
        required=False,
        initial="all",
        label="Question Source",
    )

    # ---------------------------------------------------------
    # QUESTION YEAR
    # ---------------------------------------------------------

    source_year = forms.IntegerField(
        required=False,
        min_value=1900,
        label="Question Year",
        help_text=(
            "Only use this when practising past questions "
            "from a specific year."
        ),
    )

    # ---------------------------------------------------------
    # DIFFICULTY
    # ---------------------------------------------------------

    difficulty = forms.ChoiceField(
        choices=[
            ("all", "All Difficulties"),
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ],
        required=False,
        initial="all",
        label="Difficulty",
    )

    # ---------------------------------------------------------
    # NUMBER OF QUESTIONS
    # ---------------------------------------------------------

    number_of_questions = forms.IntegerField(
        min_value=1,
        required=False,
        label="Number of Questions",
        help_text=(
            "Leave blank to use all eligible questions."
        ),
    )

    # ---------------------------------------------------------
    # QUESTION ORDER
    # ---------------------------------------------------------

    order = forms.ChoiceField(
        choices=[
            ("sequential", "Sequential"),
            ("random", "Random"),
        ],
        initial="random",
        label="Question Order",
    )

    # ---------------------------------------------------------
    # INITIALIZATION AND DYNAMIC QUERYSETS
    # ---------------------------------------------------------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        subject_id = None
        topic_id = None

        if self.is_bound:
            subject_id = self.data.get("subject")
            topic_id = self.data.get("topic")

        else:
            subject_id = self.initial.get("subject")
            topic_id = self.initial.get("topic")

        # ExamYear represents the student's target JAMB year.
        # It is not the same as SyllabusVersion.year.

        published_questions = Question.objects.filter(
            status="published"
        )

        # -----------------------------------------------------
        # AVAILABLE SUBJECTS
        # -----------------------------------------------------

        subject_ids = published_questions.values_list(
            "subtopic__topic__syllabus_version__subject_id",
            flat=True,
        ).distinct()

        self.fields["subject"].queryset = (
            Subject.objects.filter(
                id__in=subject_ids
            )
            .order_by("name")
        )

        # -----------------------------------------------------
        # AVAILABLE TOPICS
        # -----------------------------------------------------

        if subject_id:
            topic_ids = published_questions.filter(
                subtopic__topic__syllabus_version__subject_id=subject_id
            ).values_list(
                "subtopic__topic_id",
                flat=True,
            ).distinct()

            self.fields["topic"].queryset = (
                Topic.objects.filter(
                    id__in=topic_ids
                )
                .order_by("name")
            )

        # -----------------------------------------------------
        # AVAILABLE SUBTOPICS
        # -----------------------------------------------------

        if subject_id and topic_id:
            subtopic_ids = published_questions.filter(
                subtopic__topic_id=topic_id,
                subtopic__topic__syllabus_version__subject_id=subject_id,
            ).values_list(
                "subtopic_id",
                flat=True,
            ).distinct()

            self.fields["subtopic"].queryset = (
                Subtopic.objects.filter(
                    id__in=subtopic_ids
                )
                .order_by("name")
            )

    # ---------------------------------------------------------
    # FORM VALIDATION
    # ---------------------------------------------------------

    def clean(self):
        cleaned_data = super().clean()

        exam_year = cleaned_data.get("exam_year")
        subject = cleaned_data.get("subject")
        topic = cleaned_data.get("topic")
        subtopic = cleaned_data.get("subtopic")

        source_type = cleaned_data.get("source_type")
        source_year = cleaned_data.get("source_year")

        if not exam_year:
            return cleaned_data

        # -----------------------------------------------------
        # TOPIC VALIDATION
        # -----------------------------------------------------

        if topic:

            if not subject:
                self.add_error(
                    "topic",
                    "Select a subject before selecting a topic.",
                )

            elif topic.syllabus_version.subject_id != subject.id:
                self.add_error(
                    "topic",
                    (
                        "The selected topic does not belong "
                        "to the selected subject."
                    ),
                )

        # -----------------------------------------------------
        # SUBTOPIC VALIDATION
        # -----------------------------------------------------

        if subtopic:

            if not topic:
                self.add_error(
                    "subtopic",
                    "Select a topic before selecting a subtopic.",
                )

            elif subtopic.topic_id != topic.id:
                self.add_error(
                    "subtopic",
                    (
                        "The selected subtopic does not belong "
                        "to the selected topic."
                    ),
                )

        # -----------------------------------------------------
        # QUESTION YEAR VALIDATION
        # -----------------------------------------------------

        if source_type == "past_question" and not source_year:
            self.add_error(
                "source_year",
                "Enter the year of the past questions.",
            )

        if source_type != "past_question" and source_year:
            self.add_error(
                "source_year",
                (
                    "Question Year can only be used "
                    "with Past Questions."
                ),
            )

        return cleaned_data