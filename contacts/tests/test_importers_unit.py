from datetime import date
from io import BytesIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from contacts.importers import (
    ImportResult,
    canonical_header,
    decoded_csv_lines,
    error_report_rows,
    parse_date,
    stream_import_contacts,
)
from contacts.importers import RowError


class ImporterUnitTests(SimpleTestCase):
    def test_canonical_header_maps_aliases(self):
        self.assertEqual(canonical_header("First Name"), "first_name")
        self.assertEqual(canonical_header("given name"), "first_name")
        self.assertEqual(canonical_header("Unknown Field"), "unknown_field")

    def test_parse_date_accepts_formats(self):
        self.assertEqual(parse_date("2020-01-15"), date(2020, 1, 15))
        self.assertEqual(parse_date("01/15/2020"), date(2020, 1, 15))
        self.assertEqual(parse_date("01/15/20"), date(2020, 1, 15))
        self.assertIsNone(parse_date(""))

    def test_parse_date_rejects_invalid(self):
        with self.assertRaises(ValidationError):
            parse_date("not-a-date")

    def test_import_result_failed_count(self):
        result = ImportResult(errors=[RowError(2, {}, {"first_name": "required"})])
        self.assertEqual(result.failed_count, 1)

    def test_error_report_rows_formats_csv(self):
        errors = [RowError(3, {}, {"first_name": ["Required."]})]
        rows = list(error_report_rows(errors))
        self.assertEqual(rows[0], "Row,Field,Error\r\n")
        self.assertIn("3,first_name,Required.", rows[1])

    def test_error_report_rows_handles_string_message(self):
        errors = [RowError(2, {}, {"file": "bad header"})]
        rows = list(error_report_rows(errors))
        self.assertIn("bad header", rows[1])

    def test_decoded_csv_lines_handles_partial_chunk(self):
        class ChunkFile:
            def chunks(self):
                yield b"First Name\n"
                yield b"Ada"

        lines = list(decoded_csv_lines(ChunkFile()))
        self.assertEqual("".join(lines), "First Name\nAda")


class ImporterIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_stream_import_missing_header(self):
        uploaded = SimpleUploadedFile("contacts.csv", b"", content_type="text/csv")
        result = stream_import_contacts(self.user, uploaded)
        self.assertEqual(result.imported_count, 0)
        self.assertIn("header", str(result.errors[0].errors))

    def test_stream_import_parses_birthday(self):
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            b"First Name,Last Name,Birthday\nAda,Lovelace,1815-12-10\n",
            content_type="text/csv",
        )
        result = stream_import_contacts(self.user, uploaded)
        self.assertEqual(result.imported_count, 1)
