import json

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.services.question_importer import (
    preview_question_import,
    import_questions,
)


class Command(BaseCommand):
    help = "Preview or import questions from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_file",
            type=str,
            help="Path to the JSON question file.",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save valid questions to the database.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["json_file"])

        if not file_path.is_file():
            raise CommandError(
                f"File does not exist: {file_path}"
            )

        try:
            with file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except json.JSONDecodeError as error:
            raise CommandError(
                f"Invalid JSON: {error}"
            )

        except OSError as error:
            raise CommandError(
                f"Could not read file: {error}"
            )

        if options["commit"]:
            report = import_questions(data)
        else:
            report = preview_question_import(data)

        self.stdout.write("")
        self.stdout.write("QUESTION IMPORT REPORT")
        self.stdout.write("----------------------")

        self.stdout.write(
            f"Total questions: {report['total']}"
        )

        self.stdout.write(
            f"Valid questions: {report['valid']}"
        )

        self.stdout.write(
            f"Duplicates: {report['duplicates']}"
        )

        self.stdout.write(
            f"Ready to import: {report['to_import']}"
        )

        if report["errors"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR("VALIDATION ERRORS")
            )

            for item in report["errors"]:
                self.stdout.write(
                    f"Row {item['row']}:"
                )

                for message in item["messages"]:
                    self.stdout.write(f"  - {message}")

        if report["duplicate_rows"]:
            self.stdout.write("")
            self.stdout.write("DUPLICATES")

            for item in report["duplicate_rows"]:
                self.stdout.write(
                    f"Row {item['row']}: {item['reason']}"
                )

        self.stdout.write("")

        if not options["commit"]:
            if report["ready_to_import"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Preview complete. No questions were saved."
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "Preview found errors. Correct them before importing."
                    )
                )

        elif report["saved"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import complete. {report['imported']} questions saved."
                )
            )

        else:
            self.stdout.write(
                self.style.ERROR(
                    "Import cancelled. No questions were saved."
                )
            )