import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import (
    Category,
    Subject,
    SyllabusVersion,
    Topic,
    Subtopic,
    Question,
)


def normalize_question_text(text):
    """Normalize question text for duplicate detection."""
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.casefold().split())


def get_unique_match(model, **filters):
    """Return one matching object, or an error if missing or ambiguous."""
    matches = model.objects.filter(**filters)

    if not matches.exists():
        return None, "No matching record was found."

    if matches.count() > 1:
        return None, "More than one matching record was found."

    return matches.first(), None


def resolve_subtopic(row):
    """Find the existing subtopic described by an import row."""
    category_name = row.get("category")
    subject_name = row.get("subject")
    topic_name = row.get("topic")
    subtopic_name = row.get("subtopic")
    syllabus_year = row.get("syllabus_year")

    names = {
        "category": category_name,
        "subject": subject_name,
        "topic": topic_name,
        "subtopic": subtopic_name,
    }

    for field, value in names.items():
        if not isinstance(value, str) or not value.strip():
            return None, f"{field} must be a non-empty string."

    if (
        isinstance(syllabus_year, bool)
        or not isinstance(syllabus_year, int)
        or syllabus_year < 1
    ):
        return None, "syllabus_year must be a positive integer."

    category, error = get_unique_match(
        Category,
        name__iexact=category_name.strip(),
    )

    if error:
        return None, f"Category: {error}"

    subject, error = get_unique_match(
        Subject,
        name__iexact=subject_name.strip(),
        category=category,
    )

    if error:
        return None, f"Subject: {error}"

    syllabus, error = get_unique_match(
        SyllabusVersion,
        subject=subject,
        year=syllabus_year,
    )

    if error:
        return None, f"Syllabus: {error}"

    topic, error = get_unique_match(
        Topic,
        name__iexact=topic_name.strip(),
        syllabus_version=syllabus,
    )

    if error:
        return None, f"Topic: {error}"

    subtopic, error = get_unique_match(
        Subtopic,
        name__iexact=subtopic_name.strip(),
        topic=topic,
    )

    if error:
        return None, f"Subtopic: {error}"

    return subtopic, None


def prepare_question(row):
    """Validate one row and prepare a Question object."""
    errors = []

    if not isinstance(row, dict):
        return None, ["Each question must be a JSON object."]

    subtopic, error = resolve_subtopic(row)

    if error:
        errors.append(error)

    text = row.get("text")

    if not isinstance(text, str) or not text.strip():
        errors.append("Question text must be a non-empty string.")

    options = row.get("options")

    if not isinstance(options, dict):
        errors.append("options must be an object containing A, B, C and D.")
        options = {}

    option_values = {}

    for letter in ("A", "B", "C", "D"):
        value = options.get(letter)

        if not isinstance(value, str) or not value.strip():
            errors.append(f"Option {letter} must be a non-empty string.")
        else:
            option_values[letter] = value.strip()

    correct_option = row.get("correct_option")

    if isinstance(correct_option, str):
        correct_option = correct_option.strip().upper()

    if correct_option not in ("A", "B", "C", "D"):
        errors.append("correct_option must be A, B, C or D.")

    explanation = row.get("explanation", "")

    if explanation is None:
        explanation = ""

    if not isinstance(explanation, str):
        errors.append("explanation must be a string.")

    difficulty = row.get("difficulty", "medium")

    if isinstance(difficulty, str):
        difficulty = difficulty.strip().lower()

    if difficulty not in ("easy", "medium", "hard"):
        errors.append("difficulty must be easy, medium or hard.")

    source_type = row.get("source_type")

    if isinstance(source_type, str):
        source_type = source_type.strip().lower()

    if source_type not in ("past_question", "model_question"):
        errors.append(
            "source_type must be past_question or model_question."
        )

    source_year = row.get("source_year")

    if source_type == "past_question":
        if (
            isinstance(source_year, bool)
            or not isinstance(source_year, int)
            or source_year < 1
        ):
            errors.append(
                "Past questions must have a positive source_year."
            )

    elif source_type == "model_question":
        if source_year is not None:
            errors.append(
                "Model questions cannot have a source_year."
            )

    if errors:
        return None, errors

    question = Question(
        subtopic=subtopic,
        text=text.strip(),
        option_a=option_values["A"],
        option_b=option_values["B"],
        option_c=option_values["C"],
        option_d=option_values["D"],
        correct_option=correct_option,
        explanation=explanation.strip(),
        difficulty=difficulty,
        source_type=source_type,
        source_year=source_year,
    )

    try:
        question.full_clean()
    except ValidationError as error:
        if hasattr(error, "message_dict"):
            for messages in error.message_dict.values():
                errors.extend(messages)
        else:
            errors.extend(error.messages)

    if errors:
        return None, errors

    return question, []


def prepare_import(data):
    """Validate the complete import file without saving anything."""
    report = {
        "total": 0,
        "valid": 0,
        "duplicates": 0,
        "to_import": 0,
        "errors": [],
        "duplicate_rows": [],
        "ready_to_import": False,
        "saved": False,
        "imported": 0,
    }

    if not isinstance(data, dict):
        report["errors"].append({
            "row": 0,
            "messages": ["The import file must contain a JSON object."],
        })
        return report, []

    version = data.get("format_version")

    if isinstance(version, bool) or version != 1:
        report["errors"].append({
            "row": 0,
            "messages": ["Unsupported or missing format_version. Use 1."],
        })
        return report, []

    rows = data.get("questions")

    if not isinstance(rows, list) or not rows:
        report["errors"].append({
            "row": 0,
            "messages": ["questions must be a non-empty list."],
        })
        return report, []

    report["total"] = len(rows)

    prepared_questions = []

    for row_number, row in enumerate(rows, start=1):
        question, errors = prepare_question(row)

        if errors:
            report["errors"].append({
                "row": row_number,
                "messages": errors,
            })
            continue

        prepared_questions.append((row_number, question))

    report["valid"] = len(prepared_questions)

    # Load existing questions for the relevant subtopics.
    subtopic_ids = {
        question.subtopic_id
        for _, question in prepared_questions
    }

    existing_questions = Question.objects.filter(
        subtopic_id__in=subtopic_ids
    ).only("subtopic_id", "text")

    existing_texts = {
        (
            existing.subtopic_id,
            normalize_question_text(existing.text),
        )
        for existing in existing_questions
    }

    seen_in_file = set()
    questions_to_create = []

    for row_number, question in prepared_questions:
        duplicate_key = (
            question.subtopic_id,
            normalize_question_text(question.text),
        )

        if duplicate_key in existing_texts:
            report["duplicates"] += 1

            report["duplicate_rows"].append({
                "row": row_number,
                "reason": "This question already exists in the database.",
            })

            continue

        if duplicate_key in seen_in_file:
            report["duplicates"] += 1

            report["duplicate_rows"].append({
                "row": row_number,
                "reason": "This question appears more than once in the file.",
            })

            continue

        seen_in_file.add(duplicate_key)
        questions_to_create.append(question)

    report["to_import"] = len(questions_to_create)

    report["ready_to_import"] = (
        len(report["errors"]) == 0
    )

    return report, questions_to_create


def preview_question_import(data):
    """Return an import report without saving questions."""
    report, _ = prepare_import(data)
    return report


def import_questions(data):
    """Import validated questions in one database transaction."""
    report, questions_to_create = prepare_import(data)

    if report["errors"]:
        report["saved"] = False
        report["imported"] = 0
        return report

    with transaction.atomic():
        for question in questions_to_create:
            question.save()

    report["saved"] = True
    report["imported"] = len(questions_to_create)

    return report