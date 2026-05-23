from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.exporters import contact_to_vcard, csv_contact_rows
from contacts.forms import CSVImportForm
from contacts.importers import stream_import_contacts
from contacts.models import Contact, Email, Group, Phone, Tag


class ImportExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_csv_import_requires_first_name(self):
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            b"First Name,Last Name,Email\n,NoFirst,bad@example.com\n",
            content_type="text/csv",
        )

        result = stream_import_contacts(self.user, uploaded)

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.failed_count, 1)
        self.assertIn("first_name", result.errors[0].errors)

    def test_csv_error_report_download(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["last_import_errors"] = [
            {
                "row_number": 3,
                "data": {"first_name": ""},
                "errors": {"first_name": ["First name is required."]},
            }
        ]
        session["last_import_errors_user_id"] = str(self.user.pk)
        session.save()

        response = self.client.get(reverse("contacts:csv_error_report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(b"First name is required.", b"".join(response.streaming_content))

    def test_vcard_export_one(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:vcard_one", args=[contact.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BEGIN:VCARD", response.content)

    def test_csv_export_download(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:csv_export"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_csv_import_partially_succeeds_and_reports_row_errors(self):
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            (
                "First Name,Last Name,Email,Phone\n"
                "Ada,Lovelace,ada@example.com,(415) 555-2671\n"
                ",NoFirst,bad@example.com,555\n"
            ).encode(),
            content_type="text/csv",
        )

        result = stream_import_contacts(self.user, uploaded)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(Contact.objects.get().phone, "+14155552671")

    def test_csv_import_rejects_oversized_file(self):
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="text/csv",
        )
        form = CSVImportForm(files={"file": uploaded})

        self.assertFalse(form.is_valid())
        self.assertIn("5 MB", form.errors["file"][0])

    def test_csv_export_respects_active_filter(self):
        Contact.objects.create(owner=self.user, first_name="Active", last_name="One")
        Contact.objects.create(
            owner=self.user,
            first_name="Archived",
            last_name="Two",
            is_archived=True,
        )

        active_rows = list(csv_contact_rows(Contact.objects.for_user(self.user).active()))
        payload = "".join(active_rows)

        self.assertIn("Active,One,", payload)
        self.assertNotIn("Archived,Two,", payload)

    def test_csv_export_yields_streaming_rows(self):
        Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )

        payload = "".join(csv_contact_rows(Contact.objects.for_user(self.user)))

        self.assertIn("First Name", payload)
        self.assertIn("Ada", payload)
        self.assertNotIn("Favorite", payload)
        self.assertNotIn("Archived", payload)

    def test_vcard_escapes_values_and_folds_long_lines(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            last_name="Love;lace",
            notes="comma, semicolon; " + ("x" * 90),
        )
        Email.objects.create(contact=contact, address="ada@example.com")
        Phone.objects.create(contact=contact, number="+14155552671")

        payload = contact_to_vcard(contact)

        self.assertIn("VERSION:3.0", payload)
        self.assertIn("Love\\;lace", payload)
        self.assertIn("comma\\, semicolon\\;", payload)
        self.assertIn("\r\n ", payload)
        self.assertTrue(payload.endswith("\r\n"))

    def test_vcard_reference_shape(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="+14155552671",
            company="Analytical Engines",
            birthday=date(1815, 12, 10),
        )
        Phone.objects.create(contact=contact, number="+14155552671", label=Phone.MOBILE)
        Email.objects.create(contact=contact, address="ada@example.com", label=Email.OTHER)

        payload = contact_to_vcard(contact)

        self.assertIn("BEGIN:VCARD", payload)
        self.assertIn("VERSION:3.0", payload)
        self.assertIn("FN:Ada Lovelace", payload)
        self.assertIn("N:Lovelace;Ada;;;", payload)
        self.assertIn("EMAIL:ada@example.com", payload)
        self.assertIn("TEL;TYPE=CELL:+14155552671", payload)
        self.assertIn("ORG:Analytical Engines", payload)
        self.assertIn("BDAY:1815-12-10", payload)
        self.assertIn("END:VCARD", payload)
