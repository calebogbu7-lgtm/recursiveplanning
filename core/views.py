
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    PracticeSelectionForm,
    StudentRegistrationForm,
)
from .models import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
    StudentProfile,
    Subject,
    Subtopic,
    Topic,
)
from .services.question_selector import select_questions


def home(request):
    return render(request, "core/home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                form.save()

            messages.success(
                request,
                "Your account has been created successfully. Please log in.",
            )
            return redirect("student_login")
    else:
        form = StudentRegistrationForm()

    return render(
        request,
        "core/register.html",
        {"form": form},
    )


def student_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin:index")

        return redirect("student_dashboard")

    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=identifier,
            password=password,
        )

        if user is None and identifier:
            email_user = (
                User.objects.filter(email__iexact=identifier)
                .order_by("id")
                .first()
            )

            if email_user is not None:
                user = authenticate(
                    request,
                    username=email_user.username,
                    password=password,
                )

        if user is not None:
            login(request, user)

            if user.is_staff:
                return redirect("admin:index")

            if not StudentProfile.objects.filter(user=user).exists():
                logout(request)

                messages.error(
                    request,
                    (
                        "This student account does not have a student "
                        "profile. Please contact the administrator."
                    ),
                )
                return redirect("student_login")

            return redirect("student_dashboard")

        messages.error(
            request,
            "Invalid username/email or password.",
        )

    return render(request, "core/login.html")


def student_logout(request):
    if request.method == "POST":
        logout(request)

    return redirect("home")


@login_required(login_url="student_login")
def student_dashboard(request):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    attempts = list(
        PracticeAttempt.objects.filter(
            student=profile,
            submitted_at__isnull=False,
        )
        .select_related(
            "subtopic",
            "subtopic__topic",
            "subtopic__topic__syllabus_version",
            "subtopic__topic__syllabus_version__subject",
        )
        .order_by("-submitted_at")
    )

    sessions = list(
        PracticeSession.objects.filter(
            student=profile,
            status="submitted",
            subtopic__isnull=True,
        )
        .select_related(
            "exam_year",
            "subject",
            "topic",
            "topic__syllabus_version",
            "topic__syllabus_version__subject",
        )
        .order_by("-submitted_at")
    )

    completed_attempts = len(attempts) + len(sessions)

    total_questions = sum(
        attempt.total_questions
        for attempt in attempts
    )

    total_correct = sum(
        attempt.score or 0
        for attempt in attempts
    )

    for session in sessions:
        total_questions += session.question_count
        total_correct += session.score or 0

    accuracy = (
        round((total_correct / total_questions) * 100, 1)
        if total_questions > 0
        else 0
    )

    subject_data = {}
    topic_data = {}
    practice_history = []

    def add_performance(subject, topic, score, total):
        if subject is not None:
            if subject.id not in subject_data:
                subject_data[subject.id] = {
                    "name": subject.name,
                    "attempts": 0,
                    "questions": 0,
                    "correct": 0,
                }

            subject_data[subject.id]["attempts"] += 1
            subject_data[subject.id]["questions"] += total
            subject_data[subject.id]["correct"] += score

        if topic is not None:
            if topic.id not in topic_data:
                topic_data[topic.id] = {
                    "name": topic.name,
                    "subject": (
                        subject.name if subject is not None else "Unknown"
                    ),
                    "attempts": 0,
                    "questions": 0,
                    "correct": 0,
                }

            topic_data[topic.id]["attempts"] += 1
            topic_data[topic.id]["questions"] += total
            topic_data[topic.id]["correct"] += score

    for attempt in attempts:
        topic = attempt.subtopic.topic
        subject = topic.syllabus_version.subject

        score = attempt.score or 0
        total = attempt.total_questions

        attempt_accuracy = (
            round((score / total) * 100, 1)
            if total > 0
            else 0
        )

        add_performance(subject, topic, score, total)

        practice_history.append(
            {
                "type": "Subtopic Practice",
                "subject": subject.name,
                "topic": topic.name,
                "subtopic": attempt.subtopic.name,
                "score": score,
                "total_questions": total,
                "accuracy": attempt_accuracy,
                "submitted_at": attempt.submitted_at,
            }
        )

    for session in sessions:
        topic = session.topic
        subject = session.subject

        if subject is None and topic is not None:
            subject = topic.syllabus_version.subject

        score = session.score or 0
        total = session.question_count

        session_accuracy = (
            round((score / total) * 100, 1)
            if total > 0
            else 0
        )

        add_performance(subject, topic, score, total)

        practice_history.append(
            {
                "type": session.get_mode_display(),
                "subject": (
                    subject.name if subject is not None else "General Practice"
                ),
                "topic": topic.name if topic is not None else "—",
                "subtopic": "—",
                "score": score,
                "total_questions": total,
                "accuracy": session_accuracy,
                "submitted_at": session.submitted_at,
            }
        )

    subject_performance = []

    for data in subject_data.values():
        data["accuracy"] = (
            round((data["correct"] / data["questions"]) * 100, 1)
            if data["questions"] > 0
            else 0
        )
        subject_performance.append(data)

    topic_performance = []

    for data in topic_data.values():
        data["accuracy"] = (
            round((data["correct"] / data["questions"]) * 100, 1)
            if data["questions"] > 0
            else 0
        )
        topic_performance.append(data)

    subject_performance.sort(
        key=lambda item: item["accuracy"],
        reverse=True,
    )

    topic_performance.sort(
        key=lambda item: item["accuracy"],
        reverse=True,
    )

    practice_history.sort(
        key=lambda item: item["submitted_at"],
        reverse=True,
    )

    return render(
        request,
        "core/dashboard.html",
        {
            "profile": profile,
            "completed_attempts": completed_attempts,
            "total_questions": total_questions,
            "total_correct": total_correct,
            "accuracy": accuracy,
            "practice_history": practice_history,
            "subject_performance": subject_performance,
            "topic_performance": topic_performance,
        },
    )


@login_required(login_url="student_login")
def practice(request):
    return redirect("practice_setup")


@login_required(login_url="student_login")
def practice_setup(request):
    if request.method == "POST":
        form = PracticeSelectionForm(request.POST)

        if form.is_valid():
            profile = get_object_or_404(
                StudentProfile,
                user=request.user,
            )

            mode = form.cleaned_data["mode"]
            subject = form.cleaned_data["subject"]
            topic = form.cleaned_data["topic"]
            subtopic = form.cleaned_data["subtopic"]
            source_type = form.cleaned_data["source_type"]
            source_year = form.cleaned_data["source_year"]

            difficulty = form.cleaned_data["difficulty"] or "all"

            number_of_questions = form.cleaned_data[
                "number_of_questions"
            ]

            order = form.cleaned_data["order"]

            # An empty duration must become None, not an empty string.
            duration_minutes = (
                form.cleaned_data["duration_minutes"] or None
            )

            try:
                selected_questions = select_questions(
                    subject=subject,
                    topic=topic,
                    subtopic=subtopic,
                    source_type=source_type,
                    source_year=source_year,
                    difficulty=difficulty,
                    number_of_questions=number_of_questions,
                    order=order,
                )

            except ValueError as error:
                form.add_error(
                    "number_of_questions",
                    str(error),
                )

            else:
                if not selected_questions:
                    form.add_error(
                        "number_of_questions",
                        (
                            "No published questions are available "
                            "for the selected criteria."
                        ),
                    )

                else:
                    now = timezone.now()
                    ends_at = None

                    if mode == "normal_exam":
                        ends_at = now + timedelta(
                            minutes=duration_minutes
                        )

                    with transaction.atomic():
                        session = PracticeSession.objects.create(
                            student=profile,
                            exam_year=None,
                            mode=mode,
                            subject=subject,
                            topic=topic,
                            subtopic=(
                                subtopic
                                if mode == "practice"
                                else None
                            ),
                            source_type=source_type or "all",
                            source_year=source_year,
                            difficulty=(
                                difficulty
                                if difficulty != "all"
                                else None
                            ),
                            question_count=len(selected_questions),
                            order_mode=order,
                            duration_minutes=duration_minutes,
                            ends_at=ends_at,
                            status="in_progress",
                        )

                        PracticeSessionQuestion.objects.bulk_create(
                            [
                                PracticeSessionQuestion(
                                    session=session,
                                    question=question,
                                    position=position,
                                )
                                for position, question in enumerate(
                                    selected_questions
                                )
                            ]
                        )

                    mode_label = (
                        "Normal Exam"
                        if mode == "normal_exam"
                        else "Practice"
                    )

                    messages.success(
                        request,
                        (
                            f"{mode_label} session started with "
                            f"{len(selected_questions)} question(s)."
                        ),
                    )

                    return redirect(
                        "practice_session_question",
                        session_id=session.id,
                        position=1,
                    )

    else:
        form = PracticeSelectionForm()

    return render(
        request,
        "core/practice_setup.html",
        {"form": form},
    )


@login_required(login_url="student_login")
def practice_session_question(request, session_id, position):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    session = get_object_or_404(
        PracticeSession.objects.select_related(
            "exam_year",
            "subject",
            "topic",
            "subtopic",
        ),
        id=session_id,
        student=profile,
    )

    if session.status == "submitted":
        return redirect(
            "practice_session_results",
            session_id=session.id,
        )

    if session.status != "in_progress":
        return redirect("practice_setup")

    if (
        session.mode == "normal_exam"
        and session.ends_at is not None
        and timezone.now() >= session.ends_at
    ):
        return submit_practice_session(request, session)

    questions = list(
        session.session_questions.select_related(
            "question",
        ).order_by("position")
    )

    if not questions:
        messages.error(
            request,
            "This practice session has no questions.",
        )

        session.status = "abandoned"
        session.save(update_fields=["status"])

        return redirect("practice_setup")

    total_questions = len(questions)

    if position < 1 or position > total_questions:
        return redirect(
            "practice_session_question",
            session_id=session.id,
            position=1,
        )

    current = questions[position - 1]

    if request.method == "POST":
        action = request.POST.get("action")

        if action in {"next", "previous", "submit"}:
            selected_option = request.POST.get("answer")

            if selected_option in {"A", "B", "C", "D"}:
                current.selected_option = selected_option
                current.answered_at = timezone.now()

                if session.mode == "practice":
                    current.is_correct = (
                        selected_option
                        == current.question.correct_option
                    )

                    current.save(
                        update_fields=[
                            "selected_option",
                            "answered_at",
                            "is_correct",
                        ]
                    )

                else:
                    current.save(
                        update_fields=[
                            "selected_option",
                            "answered_at",
                        ]
                    )

        if action == "previous":
            return redirect(
                "practice_session_question",
                session_id=session.id,
                position=max(1, position - 1),
            )

        if action == "next":
            return redirect(
                "practice_session_question",
                session_id=session.id,
                position=min(total_questions, position + 1),
            )

        if action == "submit":
            unanswered_count = session.session_questions.filter(
                selected_option__isnull=True,
            ).count()

            if unanswered_count > 0:
                return render(
                    request,
                    "core/practice_session_question.html",
                    {
                        "session": session,
                        "current": current,
                        "position": position,
                        "total_questions": total_questions,
                        "questions": questions,
                        "unanswered_count": unanswered_count,
                        "show_submit_confirmation": True,
                        "remaining_seconds": get_remaining_seconds(
                            session
                        ),
                    },
                )

            return submit_practice_session(request, session)

        if action == "confirm_submit":
            return submit_practice_session(request, session)

    return render(
        request,
        "core/practice_session_question.html",
        {
            "session": session,
            "current": current,
            "position": position,
            "total_questions": total_questions,
            "questions": questions,
            "unanswered_count": session.session_questions.filter(
                selected_option__isnull=True,
            ).count(),
            "show_submit_confirmation": False,
            "remaining_seconds": get_remaining_seconds(session),
        },
    )


def get_remaining_seconds(session):
    if session.mode != "normal_exam" or session.ends_at is None:
        return None

    remaining = (
        session.ends_at - timezone.now()
    ).total_seconds()

    return max(0, int(remaining))


def submit_practice_session(request, session):
    with transaction.atomic():
        session = PracticeSession.objects.select_for_update().get(
            id=session.id,
        )

        if session.status == "submitted":
            return redirect(
                "practice_session_results",
                session_id=session.id,
            )

        if session.status != "in_progress":
            return redirect("practice_setup")

        questions = list(
            session.session_questions.select_related(
                "question",
            ).order_by("position")
        )

        score = 0

        for session_question in questions:
            selected_option = session_question.selected_option

            session_question.is_correct = (
                selected_option is not None
                and selected_option
                == session_question.question.correct_option
            )

            if session_question.is_correct:
                score += 1

            session_question.save(
                update_fields=["is_correct"],
            )

        session.score = score
        session.status = "submitted"
        session.submitted_at = timezone.now()

        session.save(
            update_fields=[
                "score",
                "status",
                "submitted_at",
            ]
        )

        if session.subtopic is not None:
            PracticeAttempt.objects.create(
                student=session.student,
                subtopic=session.subtopic,
                total_questions=len(questions),
                score=score,
                submitted_at=session.submitted_at,
            )

    return redirect(
        "practice_session_results",
        session_id=session.id,
    )


@login_required(login_url="student_login")
def practice_session_results(request, session_id):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    session = get_object_or_404(
        PracticeSession.objects.select_related(
            "exam_year",
            "subject",
            "topic",
            "subtopic",
        ),
        id=session_id,
        student=profile,
    )

    if session.status != "submitted":
        return redirect(
            "practice_session_question",
            session_id=session.id,
            position=1,
        )

    session_questions = list(
        session.session_questions.select_related(
            "question",
        ).order_by("position")
    )

    results = []

    for session_question in session_questions:
        question = session_question.question

        option_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }

        results.append(
            {
                "position": session_question.position,
                "question": question,
                "selected_option": session_question.selected_option,
                "selected_text": (
                    option_text.get(session_question.selected_option)
                    if session_question.selected_option
                    else None
                ),
                "correct_option": question.correct_option,
                "correct_text": option_text[question.correct_option],
                "is_correct": session_question.is_correct,
                "explanation": question.explanation,
            }
        )

    total_questions = len(session_questions)
    score = session.score or 0

    accuracy = (
        round((score / total_questions) * 100, 1)
        if total_questions > 0
        else 0
    )

    unanswered = sum(
        1
        for item in session_questions
        if item.selected_option is None
    )

    correct_count = sum(
        1
        for item in session_questions
        if item.is_correct
    )

    incorrect_count = (
        total_questions - correct_count - unanswered
    )

    return render(
        request,
        "core/practice_session_results.html",
        {
            "session": session,
            "results": results,
            "score": score,
            "total_questions": total_questions,
            "accuracy": accuracy,
            "unanswered": unanswered,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
        },
    )


@login_required(login_url="student_login")
def subject_detail(request, subject_id):
    subject = get_object_or_404(
        Subject,
        id=subject_id,
    )

    return render(
        request,
        "core/subject_detail.html",
        {"subject": subject},
    )


@login_required(login_url="student_login")
def topic_detail(request, topic_id):
    topic = get_object_or_404(
        Topic,
        id=topic_id,
    )

    return render(
        request,
        "core/topic_detail.html",
        {"topic": topic},
    )


@login_required(login_url="student_login")
def subtopic_detail(request, subtopic_id):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    subtopic = get_object_or_404(
        Subtopic,
        id=subtopic_id,
    )

    questions = list(
        subtopic.questions.filter(
            status="published"
        ).order_by("id")
    )

    if not questions:
        return render(
            request,
            "core/subtopic_detail.html",
            {
                "subtopic": subtopic,
                "questions": [],
            },
        )

    session_key = f"practice_{subtopic.id}"
    practice_data = request.session.get(session_key)

    if practice_data and (
        practice_data.get("user_id") != request.user.id
        or practice_data.get("subtopic_id") != subtopic.id
    ):
        request.session.pop(session_key, None)
        practice_data = None

    if practice_data and practice_data.get("submitted"):
        return redirect(
            "practice_results",
            subtopic_id=subtopic.id,
        )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            attempt = PracticeAttempt.objects.create(
                student=profile,
                subtopic=subtopic,
                total_questions=len(questions),
            )

            request.session[session_key] = {
                "user_id": request.user.id,
                "subtopic_id": subtopic.id,
                "attempt_id": attempt.id,
                "current_index": 0,
                "answers": {},
                "submitted": False,
                "started": True,
            }

            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

        if action in {"next", "previous"}:
            if not practice_data or not practice_data.get("started"):
                return redirect(
                    "subtopic_detail",
                    subtopic_id=subtopic.id,
                )

            question_id = request.POST.get("question_id")
            selected_option = request.POST.get("answer")

            valid_question_ids = {
                str(question.id) for question in questions
            }

            if (
                question_id in valid_question_ids
                and selected_option in {"A", "B", "C", "D"}
            ):
                practice_data["answers"][question_id] = selected_option

            current_index = practice_data["current_index"]

            if action == "next":
                current_index += 1
            else:
                current_index -= 1

            practice_data["current_index"] = max(
                0,
                min(current_index, len(questions) - 1),
            )

            request.session[session_key] = practice_data

            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

        if action == "submit":
            if not practice_data or not practice_data.get("started"):
                return redirect(
                    "subtopic_detail",
                    subtopic_id=subtopic.id,
                )

            question_id = request.POST.get("question_id")
            selected_option = request.POST.get("answer")

            valid_question_ids = {
                str(question.id) for question in questions
            }

            if (
                question_id in valid_question_ids
                and selected_option in {"A", "B", "C", "D"}
            ):
                practice_data["answers"][question_id] = selected_option

            unanswered = [
                question
                for question in questions
                if str(question.id) not in practice_data["answers"]
            ]

            if unanswered and request.POST.get("confirm") != "yes":
                request.session[session_key] = practice_data

                current_question = questions[
                    practice_data["current_index"]
                ]

                return render(
                    request,
                    "core/subtopic_detail.html",
                    {
                        "subtopic": subtopic,
                        "questions": questions,
                        "current_question": current_question,
                        "current_index": practice_data["current_index"],
                        "total_questions": len(questions),
                        "selected_answer": practice_data["answers"].get(
                            str(current_question.id)
                        ),
                        "practice_started": True,
                        "show_submit_confirmation": True,
                        "unanswered_count": len(unanswered),
                    },
                )

            score = sum(
                1
                for question in questions
                if practice_data["answers"].get(str(question.id))
                == question.correct_option
            )

            attempt_id = practice_data.get("attempt_id")

            if attempt_id:
                attempt = get_object_or_404(
                    PracticeAttempt,
                    id=attempt_id,
                    student=profile,
                    subtopic=subtopic,
                )

                attempt.score = score
                attempt.submitted_at = timezone.now()
                attempt.total_questions = len(questions)

                attempt.save(
                    update_fields=[
                        "score",
                        "submitted_at",
                        "total_questions",
                    ]
                )

            practice_data["submitted"] = True
            request.session[session_key] = practice_data

            return redirect(
                "practice_results",
                subtopic_id=subtopic.id,
            )

        if action == "restart":
            request.session.pop(session_key, None)

            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

        if action == "continue":
            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

    if not practice_data or not practice_data.get("started"):
        return render(
            request,
            "core/subtopic_detail.html",
            {
                "subtopic": subtopic,
                "questions": questions,
                "practice_started": False,
                "show_submit_confirmation": False,
            },
        )

    current_index = max(
        0,
        min(
            practice_data["current_index"],
            len(questions) - 1,
        ),
    )

    practice_data["current_index"] = current_index
    request.session[session_key] = practice_data

    current_question = questions[current_index]

    return render(
        request,
        "core/subtopic_detail.html",
        {
            "subtopic": subtopic,
            "current_question": current_question,
            "current_index": current_index,
            "total_questions": len(questions),
            "selected_answer": practice_data["answers"].get(
                str(current_question.id)
            ),
            "practice_started": True,
            "show_submit_confirmation": False,
        },
    )


@login_required(login_url="student_login")
def practice_results(request, subtopic_id):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    subtopic = get_object_or_404(
        Subtopic,
        id=subtopic_id,
    )

    questions = list(
        subtopic.questions.filter(
            status="published"
        ).order_by("id")
    )

    session_key = f"practice_{subtopic.id}"
    practice_data = request.session.get(session_key)

    if not practice_data or (
        practice_data.get("user_id") != request.user.id
        or practice_data.get("subtopic_id") != subtopic.id
        or not practice_data.get("submitted")
    ):
        return redirect(
            "subtopic_detail",
            subtopic_id=subtopic.id,
        )

    answers = practice_data["answers"]
    results = []
    score = 0

    for question in questions:
        selected_option = answers.get(str(question.id))

        if selected_option == question.correct_option:
            score += 1
            result_status = "correct"
        elif selected_option is None:
            result_status = "unanswered"
        else:
            result_status = "incorrect"

        option_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }

        results.append(
            {
                "question": question,
                "selected_option": selected_option,
                "selected_text": (
                    option_text.get(selected_option)
                    if selected_option
                    else None
                ),
                "correct_option": question.correct_option,
                "correct_text": option_text[question.correct_option],
                "status": result_status,
            }
        )

    return render(
        request,
        "core/practice_results.html",
        {
            "subtopic": subtopic,
            "results": results,
            "score": score,
            "total_questions": len(questions),
        },
    )
