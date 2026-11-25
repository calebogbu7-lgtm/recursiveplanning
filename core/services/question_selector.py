import random

from core.models import Question


VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}

VALID_SOURCE_TYPES = {
    "past_question",
    "model_question",
}

VALID_ORDERS = {
    "sequential",
    "random",
}


def select_questions(
    *,
    syllabus_year,
    subject=None,
    topic=None,
    subtopic=None,
    source_type=None,
    source_year=None,
    difficulty=None,
    number_of_questions=None,
    order="random",
):
    """
    Select published questions according to the supplied criteria.

    The function first builds the eligible question pool and then
    selects the requested number of questions from that pool.

    Parameters
    ----------
    syllabus_year:
        The student's JAMB syllabus year.

    subject:
        Optional Subject object.

    topic:
        Optional Topic object.

    subtopic:
        Optional Subtopic object.

    source_type:
        Optional:
            "past_question"
            "model_question"

    source_year:
        Optional past-question year.

    difficulty:
        Optional:
            "easy"
            "medium"
            "hard"

    number_of_questions:
        Number of questions requested.
        If omitted, all eligible questions are returned.

    order:
        "sequential" or "random"

    Returns
    -------
    list[Question]
        The selected questions.

    Raises
    ------
    ValueError
        If invalid selection criteria are supplied or the requested
        number of questions is greater than the available pool.
    """

    # ---------------------------------------------------------
    # Validate syllabus year
    # ---------------------------------------------------------

    if (
        isinstance(syllabus_year, bool)
        or not isinstance(syllabus_year, int)
        or syllabus_year < 1
    ):
        raise ValueError(
            "syllabus_year must be a positive integer."
        )

    # ---------------------------------------------------------
    # Validate source type
    # ---------------------------------------------------------

    if source_type is not None:
        source_type = source_type.strip().lower()

        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                "source_type must be past_question or model_question."
            )

    # ---------------------------------------------------------
    # Validate source year
    # ---------------------------------------------------------

    if source_year is not None:
        if (
            isinstance(source_year, bool)
            or not isinstance(source_year, int)
            or source_year < 1
        ):
            raise ValueError(
                "source_year must be a positive integer."
            )

    # ---------------------------------------------------------
    # Validate difficulty
    # ---------------------------------------------------------

    if difficulty is not None:
        difficulty = difficulty.strip().lower()

        if difficulty not in VALID_DIFFICULTIES:
            raise ValueError(
                "difficulty must be easy, medium or hard."
            )

    # ---------------------------------------------------------
    # Validate question order
    # ---------------------------------------------------------

    if order not in VALID_ORDERS:
        raise ValueError(
            "order must be sequential or random."
        )

    # ---------------------------------------------------------
    # Validate question count
    # ---------------------------------------------------------

    if number_of_questions is not None:
        if (
            isinstance(number_of_questions, bool)
            or not isinstance(number_of_questions, int)
            or number_of_questions < 1
        ):
            raise ValueError(
                "number_of_questions must be a positive integer."
            )

    # ---------------------------------------------------------
    # Start with published questions belonging to the
    # student's syllabus year.
    # ---------------------------------------------------------

    questions = Question.objects.filter(
        status="published",
        subtopic__topic__syllabus_version__year=syllabus_year,
    )

    # ---------------------------------------------------------
    # Optional subject filter
    # ---------------------------------------------------------

    if subject is not None:
        questions = questions.filter(
            subtopic__topic__syllabus_version__subject=subject,
        )

    # ---------------------------------------------------------
    # Optional topic filter
    # ---------------------------------------------------------

    if topic is not None:
        questions = questions.filter(
            subtopic__topic=topic,
        )

    # ---------------------------------------------------------
    # Optional subtopic filter
    # ---------------------------------------------------------

    if subtopic is not None:
        questions = questions.filter(
            subtopic=subtopic,
        )

    # ---------------------------------------------------------
    # Optional question source filter
    # ---------------------------------------------------------

    if source_type is not None:
        questions = questions.filter(
            source_type=source_type,
        )

    # ---------------------------------------------------------
    # Source year only applies to past questions.
    #
    # This means that even if source_type was not explicitly
    # supplied, choosing a source year will only return
    # past questions from that year.
    # ---------------------------------------------------------

    if source_year is not None:
        questions = questions.filter(
            source_type="past_question",
            source_year=source_year,
        )

    # ---------------------------------------------------------
    # Optional difficulty filter
    # ---------------------------------------------------------

    if difficulty is not None:
        questions = questions.filter(
            difficulty=difficulty,
        )

    # ---------------------------------------------------------
    # Remove duplicate questions that could result from
    # relationship joins.
    # ---------------------------------------------------------

    questions = questions.distinct()

    # ---------------------------------------------------------
    # Determine the number of eligible questions.
    # ---------------------------------------------------------

    available_count = questions.count()

    # ---------------------------------------------------------
    # No eligible questions.
    # ---------------------------------------------------------

    if available_count == 0:
        return []

    # ---------------------------------------------------------
    # If no question count was supplied, return the entire
    # eligible pool.
    # ---------------------------------------------------------

    if number_of_questions is None:

        if order == "random":
            selected_questions = list(questions)

            random.shuffle(selected_questions)

            return selected_questions

        return list(
            questions.order_by("id")
        )

    # ---------------------------------------------------------
    # Do not silently return fewer questions than requested.
    # ---------------------------------------------------------

    if number_of_questions > available_count:
        raise ValueError(
            f"Only {available_count} question(s) are available "
            f"for the selected criteria, but "
            f"{number_of_questions} were requested."
        )

    # ---------------------------------------------------------
    # Sequential selection.
    #
    # Questions are returned in their database ID order.
    # ---------------------------------------------------------

    if order == "sequential":
        return list(
            questions.order_by("id")[
                :number_of_questions
            ]
        )

    # ---------------------------------------------------------
    # Random selection.
    #
    # Random questions are selected ONLY from the eligible
    # question pool.
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Retrieve the selected Question objects.
    # ---------------------------------------------------------

    selected_questions = list(
        Question.objects.filter(
            id__in=selected_ids,
        )
    )

    # ---------------------------------------------------------
    # Rebuild the questions in the exact random order produced
    # by random.sample().
    # ---------------------------------------------------------

    questions_by_id = {
        question.id: question
        for question in selected_questions
    }

    return [
        questions_by_id[question_id]
        for question_id in selected_ids
    ]