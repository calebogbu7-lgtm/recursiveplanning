from django.urls import path
from .views import home, practice, subject_detail

urlpatterns = [
    path("", home, name="home"),
    path("practice/", practice, name="practice"),
    path("practice/subject/<int:subject_id>/", subject_detail, name="subject_detail"),
]

def subject_detail(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    return render(request, "core/subject_detail.html", {
        "subject": subject
    })