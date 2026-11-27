from django.urls import path

from .views import (
    home,
    practice,
    practice_results,
    practice_setup,
    practice_session_question,
    practice_session_results,
    register,
    student_dashboard,
    student_login,
    student_logout,
    submit_practice_session,
    subject_detail,
    subtopic_detail,
    topic_detail,
)


urlpatterns = [
    path(
        "",
        home,
        name="home",
    ),

    # Student account pages
    path(
        "register/",
        register,
        name="register",
    ),

    path(
        "login/",
        student_login,
        name="student_login",
    ),

    path(
        "logout/",
        student_logout,
        name="student_logout",
    ),

    path(
        "dashboard/",
        student_dashboard,
        name="student_dashboard",
    ),

    # Practice pages
    path(
        "practice/",
        practice,
        name="practice",
    ),

    path(
        "practice/setup/",
        practice_setup,
        name="practice_setup",
    ),

    path(
        "practice/session/<int:session_id>/question/<int:position>/",
        practice_session_question,
        name="practice_session_question",
    ),

    path(
        "practice/session/<int:session_id>/submit/",
        submit_practice_session,
        name="submit_practice_session",
    ),

    path(
        "practice/session/<int:session_id>/results/",
        practice_session_results,
        name="practice_session_results",
    ),

    path(
        "practice/subject/<int:subject_id>/",
        subject_detail,
        name="subject_detail",
    ),

    path(
        "practice/topic/<int:topic_id>/",
        topic_detail,
        name="topic_detail",
    ),

    path(
        "practice/subtopic/<int:subtopic_id>/",
        subtopic_detail,
        name="subtopic_detail",
    ),

    path(
        "practice/subtopic/<int:subtopic_id>/results/",
        practice_results,
        name="practice_results",
    ),
]