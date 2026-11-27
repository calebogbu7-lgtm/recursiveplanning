import random

from core.models import Question


VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}

VALID_SOURCE_TYPES = {
    "all",
    "past_question",
    "model_question",
}

VALID_ORDERS = {
    "sequential",
    "random",
}


def select_questions(
    *,
    syllabus_year=None,
    subject=None,
    topic=None,
    subtopic=None,
    source_type="all",
    source_year=None,
    difficulty="all",
    number_of_questions=None,
    order="random",
):
    """
    Select published questions according to the supplied criteria.

    ExamYear is the student's target JAMB exam year.

    SyllabusVersion.year is the year of the content.

    Question.source_year is the year of a past question.

    These three year values are separate.

    Selecting 'all' for source_type or difficulty
    means no restriction is applied for that setting.

    A question count is required. The selector will never
    automatically return all available questions when the
    count is missing.
    """

    # Validate syllabus year.
    if syllabus_year is not None:
        if (
            isinstance(syllabus_year, bool)
            or not isinstance(syllabus_year, int)
            or syllabus_year < 1
        ):
            raise ValueError(
                "syllabus_year must be a positive integer."
            )

    # Validate source type.
    if source_type is not None:
        source_type = source_type.strip().lower()

        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                "source_type must be all, past_question "
                "or model_question."
            )

    # Validate question year.
    if source_year is not None:
        if (
            isinstance(source_year, bool)
            or not isinstance(source_year, int)
            or source_year < 1900
        ):
            raise ValueError(
                "source_year must be a valid question year."
            )

    # Validate difficulty.
    if difficulty is not None:
        difficulty = difficulty.strip().lower()

        if difficulty not in VALID_DIFFICULTIES | {"all"}:
            raise ValueError(
                "difficulty must be all, easy, medium or hard."
            )

    # Validate order.
    if order not in VALID_ORDERS:
        raise ValueError(
            "order must be sequential or random."
        )

    # Question count is required.
    if number_of_questions is None:
        raise ValueError(
            "Please enter the number of questions."
        )

    if (
        isinstance(number_of_questions, bool)
        or not isinstance(number_of_questions, int)
        or number_of_questions < 1
    ):
        raise ValueError(
            "number_of_questions must be a positive integer."
        )

    # Start with published questions only.
    questions = Question.objects.filter(
        status="published",
    )

    # Optional syllabus/content-year filter.
    if syllabus_year is not None:
        questions = questions.filter(
            subtopic__topic__syllabus_version__year=syllabus_year,
        )

    # Optional subject filter.
    if subject is not None:
        questions = questions.filter(
            subtopic__topic__syllabus_version__subject=subject,
        )

    # Optional topic filter.
    if topic is not None:
        questions = questions.filter(
            subtopic__topic=topic,
        )

    # Optional subtopic filter.
    if subtopic is not None:
        questions = questions.filter(
            subtopic=subtopic,
        )

    # Filter by source type only when a specific type is selected.
    if source_type in {
        "past_question",
        "model_question",
    }:
        questions = questions.filter(
            source_type=source_type,
        )

    # Question year applies only to past questions.
    if source_year is not None:
        questions = questions.filter(
            source_type="past_question",
            source_year=source_year,
        )

    # Filter by difficulty only when a specific difficulty is selected.
    if difficulty in VALID_DIFFICULTIES:
        questions = questions.filter(
            difficulty=difficulty,
        )

    questions = questions.distinct()

    available_count = questions.count()

    if available_count == 0:
        return []

    # Prevent requesting more questions than are available.
    if number_of_questions > available_count:
        raise ValueError(
            f"Only {available_count} question(s) are available "
            f"for the selected criteria, but "
            f"{number_of_questions} were requested."
        )

    # Sequential selection.
    if order == "sequential":
        return list(
            questions.order_by("id")[
                :number_of_questions
            ]
        )

    # Random selection.
    question_ids = list(
        questions.values_list(
            "id",
            flat=True,
        )
    )

    selected_ids = random.sample(
        question_ids,
        number_of_questions,
    )

    selected_questions = list(
        Question.objects.filter(
            id__in=selected_ids,
        )
    )

    questions_by_id = {
        question.id: question
        for question in selected_questions
    }

    return [
        questions_by_id[question_id]
        for question_id in selected_ids
    ]