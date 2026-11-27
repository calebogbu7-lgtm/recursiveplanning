from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
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
    Question,
    StudentProfile,
    Subject,
    Subtopic,
    Topic,
)

from .services.question_selector import select_questions


# =========================================================
# HOME
# =========================================================

def home(request):
    return render(request, "core/home.html")


# =========================================================
# STUDENT REGISTRATION
# =========================================================

def register(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Your account has been created successfully. You can now log in.",
            )

            return redirect("student_login")
    else:
        form = StudentRegistrationForm()

    return render(
        request,
        "core/register.html",
        {"form": form},
    )


# =========================================================
# STUDENT LOGIN
# =========================================================

def student_login(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("student_dashboard")

        messages.error(
            request,
            "Invalid username or password.",
        )

    return render(request, "core/login.html")


# =========================================================
# STUDENT LOGOUT
# =========================================================

@login_required(login_url="student_login")
def student_logout(request):
    if request.method == "POST":
        logout(request)

        messages.success(
            request,
            "You have been logged out successfully.",
        )

        return redirect("student_login")

    return redirect("student_dashboard")


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required(login_url="student_login")
def student_dashboard(request):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    # -----------------------------------------------------
    # Completed subtopic practice attempts
    #
    # These records are created when a PracticeSession has
    # a selected subtopic. Their sessions are excluded from
    # the general-session query below to prevent duplicates.
    # -----------------------------------------------------

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
        .order_by(
            "-submitted_at",
            "-started_at",
        )
    )

    # -----------------------------------------------------
    # Completed general practice and Normal Exam sessions
    #
    # Subtopic sessions are represented by PracticeAttempt.
    # -----------------------------------------------------

    sessions = list(
        PracticeSession.objects.filter(
            student=profile,
            subtopic__isnull=True,
            status="submitted",
        )
        .select_related(
            "subject",
            "topic",
        )
        .prefetch_related(
            "session_questions__question__subtopic__topic__syllabus_version__subject",
        )
        .order_by(
            "-submitted_at",
            "-started_at",
        )
    )

    # -----------------------------------------------------
    # Overall performance totals
    # -----------------------------------------------------

    total_questions = 0
    total_correct = 0
    total_incorrect = 0
    total_unanswered = 0

    # -----------------------------------------------------
    # Performance groups
    # -----------------------------------------------------

    subject_groups = {}
    topic_groups = {}

    def update_group(
        group,
        key,
        name,
        questions,
        correct,
        incorrect,
        unanswered,
        subject_name=None,
    ):
        if key not in group:
            group[key] = {
                "name": name,
                "attempts": 0,
                "questions": 0,
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
            }

            if subject_name is not None:
                group[key]["subject"] = subject_name

        group[key]["attempts"] += 1
        group[key]["questions"] += questions
        group[key]["correct"] += correct
        group[key]["incorrect"] += incorrect
        group[key]["unanswered"] += unanswered

    # -----------------------------------------------------
    # Practice history
    # -----------------------------------------------------

    practice_history = []

    # =====================================================
    # PROCESS SUBTOPIC PRACTICE ATTEMPTS
    # =====================================================

    for attempt in attempts:
        total = attempt.total_questions or 0
        correct = attempt.score or 0
        incorrect = attempt.incorrect_questions or 0
        unanswered = attempt.unanswered_questions or 0

        total_questions += total
        total_correct += correct
        total_incorrect += incorrect
        total_unanswered += unanswered

        subtopic = attempt.subtopic
        topic = subtopic.topic
        subject = topic.syllabus_version.subject

        # Subject performance
        update_group(
            group=subject_groups,
            key=subject.id,
            name=subject.name,
            questions=total,
            correct=correct,
            incorrect=incorrect,
            unanswered=unanswered,
        )

        # Topic performance
        update_group(
            group=topic_groups,
            key=(subject.id, topic.id),
            name=topic.name,
            questions=total,
            correct=correct,
            incorrect=incorrect,
            unanswered=unanswered,
            subject_name=subject.name,
        )

        attempt_accuracy = (
            round((correct / total) * 100, 1)
            if total
            else None
        )

        practice_history.append({
            "type": "Practice",
            "subject": subject.name,
            "topic": topic.name,
            "subtopic": subtopic.name,
            "score": correct,
            "total_questions": total,
            "incorrect": incorrect,
            "unanswered": unanswered,
            "accuracy": attempt_accuracy,
            "completed": attempt.submitted_at,
        })

    # =====================================================
    # PROCESS GENERAL PRACTICE AND NORMAL EXAM SESSIONS
    # =====================================================

    for session in sessions:
        session_questions = list(
            session.session_questions.all()
        )

        total = len(session_questions)

        correct = sum(
            1
            for item in session_questions
            if item.is_correct is True
        )

        incorrect = sum(
            1
            for item in session_questions
            if item.is_correct is False
        )

        unanswered = sum(
            1
            for item in session_questions
            if item.is_correct is None
        )

        total_questions += total
        total_correct += correct
        total_incorrect += incorrect
        total_unanswered += unanswered

        # -------------------------------------------------
        # Recover subject, topic and subtopic information
        # from the questions in this session.
        # -------------------------------------------------

        question_subjects = {}
        question_topics = {}
        question_subtopics = {}

        subject_question_groups = {}
        topic_question_groups = {}

        for item in session_questions:
            question_subtopic = item.question.subtopic

            if question_subtopic is None:
                continue

            question_topic = question_subtopic.topic

            question_subject = (
                question_topic
                .syllabus_version
                .subject
            )

            subject_id = question_subject.id
            topic_id = question_topic.id
            subtopic_id = question_subtopic.id

            question_subjects[subject_id] = question_subject.name
            question_topics[topic_id] = question_topic.name
            question_subtopics[subtopic_id] = question_subtopic.name

            # Subject group for this session
            if subject_id not in subject_question_groups:
                subject_question_groups[subject_id] = {
                    "subject": question_subject,
                    "questions": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                }

            # Topic group for this session
            topic_key = (subject_id, topic_id)

            if topic_key not in topic_question_groups:
                topic_question_groups[topic_key] = {
                    "subject": question_subject,
                    "topic": question_topic,
                    "questions": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "unanswered": 0,
                }

            # Add this question's result to both groups
            groups = [
                subject_question_groups[subject_id],
                topic_question_groups[topic_key],
            ]

            for group in groups:
                group["questions"] += 1

                if item.is_correct is True:
                    group["correct"] += 1
                elif item.is_correct is False:
                    group["incorrect"] += 1
                else:
                    group["unanswered"] += 1

        # -------------------------------------------------
        # Determine the session's subject label
        # -------------------------------------------------

        if session.subject:
            subject_name = session.subject.name

        elif len(question_subjects) == 1:
            subject_name = next(iter(question_subjects.values()))

        elif len(question_subjects) > 1:
            subject_name = "Multiple Subjects"

        else:
            subject_name = "General Practice"

        # -------------------------------------------------
        # Determine the session's topic label
        # -------------------------------------------------

        if session.topic:
            topic_name = session.topic.name

        elif len(question_topics) == 1:
            topic_name = next(iter(question_topics.values()))

        elif len(question_topics) > 1:
            topic_name = "Multiple Topics"

        else:
            topic_name = "—"

        # -------------------------------------------------
        # Determine the session's subtopic label
        # -------------------------------------------------

        if session.subtopic:
            subtopic_name = session.subtopic.name

        elif len(question_subtopics) == 1:
            subtopic_name = next(iter(question_subtopics.values()))

        elif len(question_subtopics) > 1:
            subtopic_name = "Multiple Subtopics"

        else:
            subtopic_name = "—"

        # -------------------------------------------------
        # Add this session's results to subject performance
        # -------------------------------------------------

        for subject_id, data in subject_question_groups.items():
            update_group(
                group=subject_groups,
                key=subject_id,
                name=data["subject"].name,
                questions=data["questions"],
                correct=data["correct"],
                incorrect=data["incorrect"],
                unanswered=data["unanswered"],
            )

        # -------------------------------------------------
        # Add this session's results to topic performance
        # -------------------------------------------------

        for topic_key, data in topic_question_groups.items():
            update_group(
                group=topic_groups,
                key=topic_key,
                name=data["topic"].name,
                questions=data["questions"],
                correct=data["correct"],
                incorrect=data["incorrect"],
                unanswered=data["unanswered"],
                subject_name=data["subject"].name,
            )

        # -------------------------------------------------
        # Session accuracy
        # -------------------------------------------------

        session_accuracy = (
            round((correct / total) * 100, 1)
            if total
            else None
        )

        # -------------------------------------------------
        # Add session to practice history
        # -------------------------------------------------

        practice_history.append({
            "type": (
                "Normal Exam"
                if session.mode == "normal_exam"
                else "Practice"
            ),
            "subject": subject_name,
            "topic": topic_name,
            "subtopic": subtopic_name,
            "score": correct,
            "total_questions": total,
            "incorrect": incorrect,
            "unanswered": unanswered,
            "accuracy": session_accuracy,
            "completed": session.submitted_at,
        })

    # =====================================================
    # OVERALL PERFORMANCE
    # =====================================================

    accuracy = (
        round((total_correct / total_questions) * 100, 1)
        if total_questions
        else 0
    )

    completed_attempts = len(attempts) + len(sessions)

    # =====================================================
    # SUBJECT PERFORMANCE
    # =====================================================

    subject_performance = []

    for data in subject_groups.values():
        questions = data["questions"]
        correct = data["correct"]

        data["accuracy"] = (
            round((correct / questions) * 100, 1)
            if questions
            else 0
        )

        subject_performance.append(data)

    subject_performance.sort(
        key=lambda item: item["name"].lower()
    )

    # =====================================================
    # TOPIC PERFORMANCE
    # =====================================================

    topic_performance = []

    for data in topic_groups.values():
        questions = data["questions"]
        correct = data["correct"]

        topic_performance.append({
            "subject": data["subject"],
            "name": data["name"],
            "attempts": data["attempts"],
            "questions": questions,
            "correct": correct,
            "incorrect": data["incorrect"],
            "unanswered": data["unanswered"],
            "accuracy": (
                round((correct / questions) * 100, 1)
                if questions
                else 0
            ),
        })

    topic_performance.sort(
        key=lambda item: (
            item["subject"].lower(),
            item["name"].lower(),
        )
    )

    # =====================================================
    # SORT PRACTICE HISTORY
    # =====================================================

    practice_history.sort(
        key=lambda item: (
            item["completed"] is not None,
            item["completed"] or timezone.now(),
        ),
        reverse=True,
    )

    # =====================================================
    # DASHBOARD CONTEXT
    # =====================================================

    context = {
        "profile": profile,
        "completed_attempts": completed_attempts,
        "total_questions": total_questions,
        "total_correct": total_correct,
        "total_incorrect": total_incorrect,
        "total_unanswered": total_unanswered,
        "accuracy": accuracy,
        "subject_performance": subject_performance,
        "topic_performance": topic_performance,
        "practice_history": practice_history,
    }

    return render(
        request,
        "core/dashboard.html",
        context,
    )


# =========================================================
# PRACTICE ENTRY
# =========================================================

@login_required(login_url="student_login")
def practice(request):
    return redirect("practice_setup")


# =========================================================
# PRACTICE SETUP
# =========================================================

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

            difficulty = (
                form.cleaned_data["difficulty"] or "all"
            )

            number_of_questions = (
                form.cleaned_data["number_of_questions"]
            )

            order = form.cleaned_data["order"]

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


# =========================================================
# PRACTICE SESSION QUESTION
# =========================================================

@login_required(login_url="student_login")
def practice_session_question(
    request,
    session_id,
    position,
):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    session = get_object_or_404(
        PracticeSession.objects.select_related(
            "subject",
            "topic",
            "subtopic",
        ),
        id=session_id,
        student=profile,
    )

    if session.status != "in_progress":
        return redirect(
            "practice_session_results",
            session_id=session.id,
        )

    if (
        session.mode == "normal_exam"
        and session.ends_at
        and timezone.now() >= session.ends_at
    ):
        return redirect(
            "submit_practice_session",
            session_id=session.id,
        )

    session_questions = list(
        session.session_questions.select_related(
            "question",
            "question__subtopic",
        )
    )

    total_questions = len(session_questions)

    if total_questions == 0:
        messages.error(
            request,
            "This session does not contain any questions.",
        )

        return redirect("practice_setup")

    if position < 1 or position > total_questions:
        return redirect(
            "practice_session_question",
            session_id=session.id,
            position=1,
        )

    session_question = session_questions[position - 1]

    if request.method == "POST":
        selected_option = request.POST.get("selected_option")

        valid_options = dict(
            Question.CORRECT_OPTION_CHOICES
        )

        if selected_option in valid_options:
            session_question.selected_option = selected_option
            session_question.answered_at = timezone.now()

            session_question.is_correct = (
                selected_option
                == session_question.question.correct_option
            )

            session_question.save(
                update_fields=[
                    "selected_option",
                    "answered_at",
                    "is_correct",
                ]
            )

        action = request.POST.get("action")

        if action == "previous":
            if position > 1:
                return redirect(
                    "practice_session_question",
                    session_id=session.id,
                    position=position - 1,
                )

        elif action == "next":
            if position < total_questions:
                return redirect(
                    "practice_session_question",
                    session_id=session.id,
                    position=position + 1,
                )

        elif action == "submit":
            return redirect(
                "submit_practice_session",
                session_id=session.id,
            )

    progress_percentage = round(
        (position / total_questions) * 100
    )

    answered_count = sum(
        1
        for item in session_questions
        if item.selected_option
    )

    context = {
        "session": session,
        "session_question": session_question,
        "question": session_question.question,
        "position": position,
        "total_questions": total_questions,
        "answered_count": answered_count,
        "progress_percentage": progress_percentage,
        "is_first_question": position == 1,
        "is_last_question": position == total_questions,
        "remaining_seconds": (
            max(
                0,
                int(
                    (
                        session.ends_at - timezone.now()
                    ).total_seconds()
                ),
            )
            if session.ends_at
            else None
        ),
    }

    return render(
        request,
        "core/practice_session_question.html",
        context,
    )


# =========================================================
# SUBMIT PRACTICE SESSION
# =========================================================

@login_required(login_url="student_login")
def submit_practice_session(
    request,
    session_id,
):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    with transaction.atomic():
        session = get_object_or_404(
            PracticeSession.objects.select_for_update(),
            id=session_id,
            student=profile,
        )

        if session.status == "submitted":
            return redirect(
                "practice_session_results",
                session_id=session.id,
            )

        session_questions = list(
            session.session_questions.select_related(
                "question",
                "question__subtopic",
            )
        )

        for session_question in session_questions:
            if session_question.selected_option:
                session_question.is_correct = (
                    session_question.selected_option
                    == session_question.question.correct_option
                )
            else:
                session_question.is_correct = None

            session_question.save(
                update_fields=["is_correct"]
            )

        correct_count = sum(
            1
            for item in session_questions
            if item.is_correct is True
        )

        incorrect_count = sum(
            1
            for item in session_questions
            if item.is_correct is False
        )

        unanswered_count = sum(
            1
            for item in session_questions
            if item.is_correct is None
        )

        session.status = "submitted"
        session.submitted_at = timezone.now()
        session.score = correct_count

        session.save(
            update_fields=[
                "status",
                "submitted_at",
                "score",
            ]
        )

        # Create a PracticeAttempt only for sessions
        # attached to a specific subtopic.

        if session.subtopic is not None:
            PracticeAttempt.objects.create(
                student=profile,
                subtopic=session.subtopic,
                started_at=session.started_at,
                submitted_at=session.submitted_at,
                score=correct_count,
                incorrect_questions=incorrect_count,
                unanswered_questions=unanswered_count,
                total_questions=len(session_questions),
            )

    return redirect(
        "practice_session_results",
        session_id=session.id,
    )


# =========================================================
# PRACTICE SESSION RESULTS
# =========================================================

@login_required(login_url="student_login")
def practice_session_results(
    request,
    session_id,
):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    session = get_object_or_404(
        PracticeSession.objects.select_related(
            "subject",
            "topic",
            "subtopic",
        ),
        id=session_id,
        student=profile,
    )

    session_questions = list(
        session.session_questions.select_related(
            "question",
            "question__subtopic",
        )
    )

    correct_count = sum(
        1
        for item in session_questions
        if item.is_correct is True
    )

    incorrect_count = sum(
        1
        for item in session_questions
        if item.is_correct is False
    )

    unanswered_count = sum(
        1
        for item in session_questions
        if item.is_correct is None
    )

    total_questions = len(session_questions)

    accuracy = (
        round(
            (correct_count / total_questions) * 100,
            1,
        )
        if total_questions
        else 0
    )

    results = []

    option_labels = dict(
        Question.CORRECT_OPTION_CHOICES
    )

    for item in session_questions:
        question = item.question

        selected_option = item.selected_option

        selected_text = (
            option_labels.get(selected_option)
            if selected_option
            else None
        )

        correct_option = question.correct_option
        correct_text = option_labels.get(correct_option)

        results.append({
            "question": question,
            "position": item.position,
            "selected_option": selected_option,
            "selected_text": selected_text,
            "correct_option": correct_option,
            "correct_text": correct_text,
            "is_correct": item.is_correct,
        })

    context = {
        "session": session,
        "results": results,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "total_questions": total_questions,
        "accuracy": accuracy,
    }

    return render(
        request,
        "core/practice_session_results.html",
        context,
    )


# =========================================================
# SUBJECT LIST
# =========================================================

@login_required(login_url="student_login")
def subject_list(request):
    get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    questions = Question.objects.filter(
        status="published",
    )

    subject_ids = (
        questions
        .values_list(
            "subtopic__topic__syllabus_version__subject_id",
            flat=True,
        )
        .distinct()
    )

    subjects = (
        Subject.objects
        .filter(id__in=subject_ids)
        .order_by("name")
    )

    return render(
        request,
        "core/subject_list.html",
        {"subjects": subjects},
    )


# =========================================================
# SUBJECT DETAIL
# =========================================================

@login_required(login_url="student_login")
def subject_detail(
    request,
    subject_id,
):
    subject = get_object_or_404(
        Subject,
        id=subject_id,
    )

    topics = (
        Topic.objects
        .filter(
            syllabus_version__subject=subject,
            subtopics__questions__status="published",
        )
        .distinct()
        .order_by("name")
    )

    return render(
        request,
        "core/subject_detail.html",
        {
            "subject": subject,
            "topics": topics,
        },
    )


# =========================================================
# TOPIC DETAIL
# =========================================================

@login_required(login_url="student_login")
def topic_detail(
    request,
    topic_id,
):
    topic = get_object_or_404(
        Topic,
        id=topic_id,
    )

    subtopics = (
        topic.subtopics
        .filter(
            questions__status="published",
        )
        .distinct()
        .order_by("name")
    )

    return render(
        request,
        "core/topic_detail.html",
        {
            "topic": topic,
            "subtopics": subtopics,
        },
    )


# =========================================================
# SUBTOPIC DETAIL
# =========================================================

@login_required(login_url="student_login")
def subtopic_detail(
    request,
    subtopic_id,
):
    subtopic = get_object_or_404(
        Subtopic,
        id=subtopic_id,
    )

    questions = list(
        Question.objects.filter(
            subtopic=subtopic,
            status="published",
        ).order_by("id")
    )

    if not questions:
        messages.error(
            request,
            "No published questions are available for this subtopic.",
        )

        return redirect("practice")

    return render(
        request,
        "core/subtopic_detail.html",
        {
            "subtopic": subtopic,
            "questions": questions,
        },
    )


# =========================================================
# PRACTICE RESULTS
# =========================================================

@login_required(login_url="student_login")
def practice_results(request):
    profile = get_object_or_404(
        StudentProfile,
        user=request.user,
    )

    attempts = (
        PracticeAttempt.objects
        .filter(student=profile)
        .select_related(
            "subtopic",
            "subtopic__topic",
            "subtopic__topic__syllabus_version",
            "subtopic__topic__syllabus_version__subject",
        )
        .order_by(
            "-submitted_at",
            "-started_at",
        )
    )

    return render(
        request,
        "core/practice_results.html",
        {"attempts": attempts},
    )