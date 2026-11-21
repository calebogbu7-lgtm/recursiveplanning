from django.shortcuts import render, get_object_or_404
from .models import Subject, Topic, Subtopic, Question


def home(request):
    return render(request, "core/home.html")


def practice(request):
    subjects = Subject.objects.all()

    return render(request, "core/practice.html", {
        "subjects": subjects
    })


def subject_detail(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    syllabuses = subject.syllabus_versions.prefetch_related(
        "topics__subtopics"
    )

    return render(request, "core/subject_detail.html", {
        "subject": subject,
        "syllabuses": syllabuses
    })


def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)

    return render(request, "core/topic_detail.html", {
        "topic": topic
    })


def subtopic_detail(request, subtopic_id):
    subtopic = get_object_or_404(Subtopic, id=subtopic_id)

    questions = subtopic.questions.filter(
        status="published"
    )

    result = None

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        selected_option = request.POST.get("answer")

        question = get_object_or_404(
            Question,
            id=question_id,
            subtopic=subtopic,
            status="published"
        )

        result = {
            "question_id": question.id,
            "selected_option": selected_option,
            "correct": selected_option == question.correct_option,
            "explanation": question.explanation,
        }

    return render(request, "core/subtopic_detail.html", {
        "subtopic": subtopic,
        "questions": questions,
        "result": result,
    })