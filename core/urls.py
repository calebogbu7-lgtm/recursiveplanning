from django.urls import path
from .views import (
    home,
    practice,
    subject_detail,
    topic_detail,
    subtopic_detail,
)

urlpatterns = [
    path("", home, name="home"),

    path(
        "practice/",
        practice,
        name="practice",
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
]