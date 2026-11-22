from django.shortcuts import get_object_or_404, redirect, render

from .models import Question, Subject, Subtopic, Topic


def home(request):
    return render(request, "core/home.html")


def practice(request):
    subjects = Subject.objects.all().order_by("name")

    return render(
        request,
        "core/practice.html",
        {
            "subjects": subjects,
        },
    )


def subject_detail(request, subject_id):
    subject = get_object_or_404(
        Subject,
        id=subject_id
    )

    syllabuses = subject.syllabus_versions.prefetch_related(
        "topics__subtopics"
    )

    return render(
        request,
        "core/subject_detail.html",
        {
            "subject": subject,
            "syllabuses": syllabuses,
        },
    )


def topic_detail(request, topic_id):
    topic = get_object_or_404(
        Topic,
        id=topic_id
    )

    return render(
        request,
        "core/topic_detail.html",
        {
            "topic": topic,
        },
    )


def subtopic_detail(request, subtopic_id):
    subtopic = get_object_or_404(
        Subtopic,
        id=subtopic_id
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

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            request.session[session_key] = {
                "current_index": 0,
                "answers": {},
                "submitted": False,
            }

            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

        if action == "answer":
            practice_data = request.session.get(
                session_key,
                {
                    "current_index": 0,
                    "answers": {},
                    "submitted": False,
                },
            )

            question_id = request.POST.get("question_id")
            selected_option = request.POST.get("answer")

            if selected_option in {"A", "B", "C", "D"}:
                practice_data["answers"][str(question_id)] = (
                    selected_option
                )

            current_index = int(
                request.POST.get(
                    "current_index",
                    practice_data["current_index"],
                )
            )

            navigation = request.POST.get("navigation")

            if navigation == "next":
                current_index += 1

            elif navigation == "previous":
                current_index -= 1

            current_index = max(
                0,
                min(current_index, len(questions) - 1),
            )

            practice_data["current_index"] = current_index

            request.session[session_key] = practice_data

            return redirect(
                "subtopic_detail",
                subtopic_id=subtopic.id,
            )

        if action == "submit":
            practice_data = request.session.get(session_key)

            if not practice_data:
                return redirect(
                    "subtopic_detail",
                    subtopic_id=subtopic.id,
                )

            unanswered = [
                question
                for question in questions
                if str(question.id)
                not in practice_data["answers"]
            ]

            if unanswered and request.POST.get("confirm") != "yes":
                return render(
                    request,
                    "core/subtopic_detail.html",
                    {
                        "subtopic": subtopic,
                        "questions": questions,
                        "practice_data": practice_data,
                        "show_submit_confirmation": True,
                        "unanswered_count": len(unanswered),
                    },
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

    practice_data = request.session.get(
        session_key,
        {
            "current_index": 0,
            "answers": {},
            "submitted": False,
        },
    )

    current_index = practice_data["current_index"]

    current_index = max(
        0,
        min(current_index, len(questions) - 1),
    )

    practice_data["current_index"] = current_index

    request.session[session_key] = practice_data

    current_question = questions[current_index]

    return render(
        request,
        "core/subtopic_detail.html",
        {
            "subtopic": subtopic,
            "questions": questions,
            "current_question": current_question,
            "current_index": current_index,
            "total_questions": len(questions),
            "selected_answer": practice_data["answers"].get(
                str(current_question.id)
            ),
            "practice_started": session_key in request.session,
            "show_submit_confirmation": False,
        },
    )


def practice_results(request, subtopic_id):
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

    if not practice_data or not practice_data.get("submitted"):
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
                "correct_text": option_text[
                    question.correct_option
                ],
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