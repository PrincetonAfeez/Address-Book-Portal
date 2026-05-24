""" Test exporters unit for the contacts app """

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from contacts.exporters import Echo, escape_vcard, fold_line, safe_csv_cell, vcards_for_contacts
from contacts.models import Contact, Email, Phone


class ExporterUnitTests(SimpleTestCase):
    def test_echo_returns_value(self):
        from contacts.csv_utils import CsvEcho

        self.assertEqual(CsvEcho().write("chunk"), "chunk")
        self.assertEqual(Echo().write("chunk"), "chunk")

    def test_escape_vcard_escapes_special_chars(self):
        self.assertEqual(escape_vcard("a;b,c\\n"), "a\\;b\\,c\\\\n")

    def test_escape_vcard_normalizes_carriage_returns(self):
        self.assertEqual(escape_vcard("line one\r\nline two\rold mac"), "line one\\nline two\\nold mac")

    def test_fold_line_splits_long_lines(self):
        line = "x" * 100
        folded = fold_line(line)
        self.assertIn("\r\n ", folded)
        self.assertLessEqual(len(folded.split("\r\n")[0].encode("utf-8")), 75)

    def test_fold_line_respects_utf8_octet_limit(self):
        line = "NOTE:" + ("é" * 40)
        folded = fold_line(line)
        for segment in folded.split("\r\n"):
            self.assertLessEqual(len(segment.encode("utf-8")), 75)

    def test_fold_line_short_unchanged(self):
        self.assertEqual(fold_line("short"), "short")

    def test_safe_csv_cell_prefixes_formula_like_values(self):
        self.assertEqual(safe_csv_cell("=SUM(A1)"), "'=SUM(A1)")
        self.assertEqual(safe_csv_cell("+14155552671"), "'+14155552671")
        self.assertEqual(safe_csv_cell("-cmd"), "'-cmd")
        self.assertEqual(safe_csv_cell("@mention"), "'@mention")
        self.assertEqual(safe_csv_cell("Ada"), "Ada")


class VcardBulkExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_vcards_for_contacts_yields_multiple(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.user, first_name="Grace")
        payload = "".join(vcards_for_contacts(Contact.objects.for_user(self.user)))
        self.assertEqual(payload.count("BEGIN:VCARD"), 2)

    def test_vcard_uses_scalar_phone_when_no_related_rows(self):
        from contacts.exporters import contact_to_vcard

        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            phone="+14155552671",
            email="ada@example.com",
        )
        payload = contact_to_vcard(contact)
        self.assertIn("TEL;TYPE=CELL:+14155552671", payload)
        self.assertIn("EMAIL:ada@example.com", payload)

    def test_vcard_maps_phone_and_email_types(self):
        from contacts.exporters import contact_to_vcard

        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        Phone.objects.create(contact=contact, number="+14155552671", label=Phone.WORK)
        Email.objects.create(contact=contact, address="work@example.com", label=Email.WORK)
        Email.objects.create(contact=contact, address="other@example.com", label=Email.OTHER)

        payload = contact_to_vcard(contact)

        self.assertIn("TEL;TYPE=WORK:+14155552671", payload)
        self.assertIn("EMAIL;TYPE=WORK:work@example.com", payload)
        self.assertIn("EMAIL:other@example.com", payload)
        self.assertNotIn("TYPE=OTHER", payload)

    def test_vcard_includes_job_title(self):
        from contacts.exporters import contact_to_vcard

        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            job_title="Engineer",
        )
        payload = contact_to_vcard(contact)
        self.assertIn("TITLE:Engineer", payload)

    def test_vcard_includes_photo_when_present(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from contacts.exporters import contact_to_vcard

        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        contact.photo.save(
            "ada.jpg",
            SimpleUploadedFile("ada.jpg", b"fake-image-bytes", content_type="image/jpeg"),
            save=True,
        )

        payload = contact_to_vcard(contact)

        self.assertIn("PHOTO;ENCODING=b;TYPE=JPEG:", payload)
