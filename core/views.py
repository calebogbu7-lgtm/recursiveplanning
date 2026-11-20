from django.shortcuts import render, get_object_or_404
from .models import Subject


def home(request):
    return render(request, "core/home.html")


def practice(request):
    subjects = Subject.objects.all()

    return render(request, "core/practice.html", {
        "subjects": subjects
    })


def subject_detail(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    return render(request, "core/subject_detail.html", {
        "subject": subject
    })