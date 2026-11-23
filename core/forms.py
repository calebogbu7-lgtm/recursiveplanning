from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ExamYear, StudentProfile


class StudentRegistrationForm(UserCreationForm):

    exam_year = forms.ModelChoiceField(
        queryset=ExamYear.objects.none(),
        empty_label="Select your JAMB exam year",
        label="JAMB Exam Year"
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
                exam_year=self.cleaned_data["exam_year"]
            )

        return user