from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import (
    Category,
    Subject,
    SyllabusVersion,
    Topic,
    Subtopic,
    Question,
    ExamYear,
    StudentProfile,
)


class ModelIntegrityTests(TestCase):

    def test_category_name_must_be_unique(self):
        Category.objects.create(name="Science")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="Science")

    def test_subject_name_unique_within_category(self):
        category = Category.objects.create(name="Science")

        Subject.objects.create(
            name="Biology",
            category=category
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subject.objects.create(
                    name="Biology",
                    category=category
                )

    def test_same_subject_allowed_in_different_categories(self):
        science = Category.objects.create(name="Science")
        arts = Category.objects.create(name="Arts")

        Subject.objects.create(
            name="Biology",
            category=science
        )

        Subject.objects.create(
            name="Biology",
            category=arts
        )

        self.assertEqual(
            Subject.objects.filter(name="Biology").count(),
            2
        )

    def test_syllabus_year_unique_per_subject(self):
        subject = Subject.objects.create(name="Biology")

        SyllabusVersion.objects.create(
            subject=subject,
            year=2026
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SyllabusVersion.objects.create(
                    subject=subject,
                    year=2026
                )

    def test_topic_name_unique_per_syllabus(self):
        subject = Subject.objects.create(name="Biology")

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=2026
        )

        Topic.objects.create(
            syllabus_version=syllabus,
            name="Cell Biology"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Topic.objects.create(
                    syllabus_version=syllabus,
                    name="Cell Biology"
                )

    def test_subtopic_name_unique_per_topic(self):
        subject = Subject.objects.create(name="Biology")

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=2026
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name="Cell Biology"
        )

        Subtopic.objects.create(
            topic=topic,
            name="Cell Structure"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subtopic.objects.create(
                    topic=topic,
                    name="Cell Structure"
                )

    def test_subtopic_cannot_delete_topic(self):
        subject = Subject.objects.create(name="Biology")

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=2026
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name="Cell Biology"
        )

        Subtopic.objects.create(
            topic=topic,
            name="Cell Structure"
        )

        with self.assertRaises(ProtectedError):
            topic.delete()


class QuestionValidationTests(TestCase):

    def create_question(self, **overrides):
        subject = Subject.objects.create(name="Biology")

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=2026
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name="Cell Biology"
        )

        subtopic = Subtopic.objects.create(
            topic=topic,
            name="Cell Structure"
        )

        data = {
            "subtopic": subtopic,
            "text": "Which organelle controls cell activities?",
            "option_a": "Nucleus",
            "option_b": "Ribosome",
            "option_c": "Mitochondrion",
            "option_d": "Vacuole",
            "correct_option": "A",
            "difficulty": "medium",
            "source_type": "model_question",
            "source_year": None,
            "status": "draft",
            "explanation": "The nucleus controls cell activities.",
        }

        data.update(overrides)

        return Question(**data)

    def test_question_text_cannot_be_blank(self):
        question = self.create_question(text="")

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_question_options_cannot_be_blank(self):
        question = self.create_question(option_a="")

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_past_question_requires_source_year(self):
        question = self.create_question(
            source_type="past_question",
            source_year=None
        )

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_model_question_cannot_have_source_year(self):
        question = self.create_question(
            source_type="model_question",
            source_year=2024
        )

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_correct_option_must_be_valid(self):
        question = self.create_question(correct_option="E")

        with self.assertRaises(ValidationError):
            question.full_clean()

    def test_valid_past_question(self):
        question = self.create_question(
            source_type="past_question",
            source_year=2024
        )

        question.full_clean()

    def test_valid_model_question(self):
        question = self.create_question(
            source_type="model_question",
            source_year=None
        )

        question.full_clean()


class StudentProfileTests(TestCase):

    def test_exam_year_must_be_unique(self):
        ExamYear.objects.create(year=2027)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExamYear.objects.create(year=2027)

    def test_student_profile_can_be_created(self):
        user = User.objects.create_user(
            username="student1",
            password="testpassword"
        )

        exam_year = ExamYear.objects.create(year=2027)

        profile = StudentProfile.objects.create(
            user=user,
            exam_year=exam_year
        )

        self.assertEqual(profile.user, user)
        self.assertEqual(profile.exam_year, exam_year)

    def test_user_can_have_only_one_student_profile(self):
        user = User.objects.create_user(
            username="student1",
            password="testpassword"
        )

        exam_year = ExamYear.objects.create(year=2027)

        StudentProfile.objects.create(
            user=user,
            exam_year=exam_year
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentProfile.objects.create(
                    user=user,
                    exam_year=exam_year
                )

    def test_exam_year_cannot_be_deleted_if_students_use_it(self):
        user = User.objects.create_user(
            username="student1",
            password="testpassword"
        )

        exam_year = ExamYear.objects.create(year=2027)

        StudentProfile.objects.create(
            user=user,
            exam_year=exam_year
        )

        with self.assertRaises(ProtectedError):
            exam_year.delete()


class StudentPracticeAccessTests(TestCase):

    def create_student(self, username="student1", exam_year=2027):
        user = User.objects.create_user(
            username=username,
            password="testpassword"
        )

        year = ExamYear.objects.create(year=exam_year)

        StudentProfile.objects.create(
            user=user,
            exam_year=year
        )

        return user

    def test_student_sees_subject_with_matching_exam_year(self):
        user = self.create_student(exam_year=2027)

        mathematics = Subject.objects.create(
            name="Mathematics"
        )

        SyllabusVersion.objects.create(
            subject=mathematics,
            year=2027
        )

        self.client.force_login(user)

        response = self.client.get("/practice/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mathematics")

    def test_student_does_not_see_subject_without_matching_exam_year(self):
        user = self.create_student(exam_year=2027)

        mathematics = Subject.objects.create(
            name="Mathematics"
        )

        SyllabusVersion.objects.create(
            subject=mathematics,
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get("/practice/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mathematics")

    def test_student_sees_only_subjects_with_matching_exam_year(self):
        user = self.create_student(exam_year=2027)

        mathematics = Subject.objects.create(
            name="Mathematics"
        )

        biology = Subject.objects.create(
            name="Biology"
        )

        SyllabusVersion.objects.create(
            subject=mathematics,
            year=2027
        )

        SyllabusVersion.objects.create(
            subject=biology,
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get("/practice/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mathematics")
        self.assertNotContains(response, "Biology")


class StudentPracticeHierarchyAccessTests(TestCase):

    def create_student(self, username="student1", exam_year=2027):
        user = User.objects.create_user(
            username=username,
            password="testpassword"
        )

        year = ExamYear.objects.create(year=exam_year)

        StudentProfile.objects.create(
            user=user,
            exam_year=year
        )

        return user

    def create_practice_hierarchy(self, year=2027):
        subject = Subject.objects.create(
            name=f"Mathematics {year}"
        )

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=year
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name=f"Algebra {year}"
        )

        subtopic = Subtopic.objects.create(
            topic=topic,
            name=f"Quadratic Equations {year}"
        )

        return subject, topic, subtopic

    def test_student_can_access_subject_for_matching_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2027
        )

        self.client.force_login(user)

        response = self.client.get(
            f"/practice/subject/{subject.id}/"
        )

        self.assertEqual(response.status_code, 200)

    def test_student_cannot_access_subject_for_different_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get(
            f"/practice/subject/{subject.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_student_cannot_access_topic_for_different_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get(
            f"/practice/topic/{topic.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_student_cannot_access_subtopic_for_different_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get(
            f"/practice/subtopic/{subtopic.id}/"
        )

        self.assertEqual(response.status_code, 404)

class StudentPracticeResultsAccessTests(TestCase):

    def create_student(self, username="student1", exam_year=2027):
        user = User.objects.create_user(
            username=username,
            password="testpassword"
        )

        year = ExamYear.objects.create(year=exam_year)

        StudentProfile.objects.create(
            user=user,
            exam_year=year
        )

        return user

    def create_practice_hierarchy(self, year=2027):
        subject = Subject.objects.create(
            name=f"Mathematics {year}"
        )

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=year
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name=f"Algebra {year}"
        )

        subtopic = Subtopic.objects.create(
            topic=topic,
            name=f"Quadratic Equations {year}"
        )

        return subject, topic, subtopic

    def test_student_can_access_results_for_matching_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2027
        )

        Question.objects.create(
            subtopic=subtopic,
            text="What is 2 + 2?",
            option_a="3",
            option_b="4",
            option_c="5",
            option_d="6",
            correct_option="B",
            status="published",
        )

        self.client.force_login(user)

        session = self.client.session
        session[f"practice_{subtopic.id}"] = {
            "user_id": user.id,
            "exam_year": 2027,
            "subtopic_id": subtopic.id,
            "current_index": 0,
            "answers": {},
            "submitted": True,
            "started": True,
        }
        session.save()

        response = self.client.get(
            f"/practice/subtopic/{subtopic.id}/results/"
        )

        self.assertEqual(response.status_code, 200)

    def test_student_cannot_access_results_for_different_exam_year(self):
        user = self.create_student(exam_year=2027)

        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2028
        )

        self.client.force_login(user)

        response = self.client.get(
            f"/practice/subtopic/{subtopic.id}/results/"
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_student_cannot_access_results(self):
        subject, topic, subtopic = self.create_practice_hierarchy(
            year=2027
        )

        response = self.client.get(
            f"/practice/subtopic/{subtopic.id}/results/"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class PracticeSessionOwnershipTests(TestCase):

    def create_student(self, username, exam_year=2027):
        user = User.objects.create_user(
            username=username,
            password="testpassword"
        )

        year, _ = ExamYear.objects.get_or_create(
            year=exam_year
        )

        StudentProfile.objects.create(
            user=user,
            exam_year=year
        )

        return user

    def create_subtopic(self):
        subject = Subject.objects.create(
            name="Mathematics"
        )

        syllabus = SyllabusVersion.objects.create(
            subject=subject,
            year=2027
        )

        topic = Topic.objects.create(
            syllabus_version=syllabus,
            name="Algebra"
        )

        return Subtopic.objects.create(
            topic=topic,
            name="Quadratic Equations"
        )

    def test_another_student_cannot_reuse_existing_practice_session(self):
        student_a = self.create_student("student_a")
        student_b = self.create_student("student_b")

        subtopic = self.create_subtopic()

        Question.objects.create(
            subtopic=subtopic,
            text="What is 2 + 2?",
            option_a="3",
            option_b="4",
            option_c="5",
            option_d="6",
            correct_option="B",
            status="published",
        )

        self.client.force_login(student_a)

        session = self.client.session
        session[f"practice_{subtopic.id}"] = {
            "user_id": student_a.id,
            "exam_year": 2027,
            "subtopic_id": subtopic.id,
            "current_index": 0,
            "answers": {},
            "submitted": False,
            "started": True,
        }
        session.save()

        self.client.force_login(student_b)

        response = self.client.get(
            f"/practice/subtopic/{subtopic.id}/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            response.context["practice_started"]
        )