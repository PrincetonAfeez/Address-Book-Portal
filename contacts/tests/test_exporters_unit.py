from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from contacts.exporters import Echo, escape_vcard, fold_line, vcards_for_contacts
from contacts.models import Contact


class ExporterUnitTests(SimpleTestCase):
    def test_echo_returns_value(self):
        self.assertEqual(Echo().write("chunk"), "chunk")

    def test_escape_vcard_escapes_special_chars(self):
        self.assertEqual(escape_vcard("a;b,c\\n"), "a\\;b\\,c\\\\n")

    def test_fold_line_splits_long_lines(self):
        line = "x" * 100
        folded = fold_line(line)
        self.assertIn("\r\n ", folded)
        self.assertLessEqual(len(folded.split("\r\n")[0]), 75)

    def test_fold_line_short_unchanged(self):
        self.assertEqual(fold_line("short"), "short")


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
        self.assertIn("TEL;TYPE=MOBILE:+14155552671", payload)
        self.assertIn("EMAIL;TYPE=OTHER:ada@example.com", payload)

    def test_vcard_includes_job_title(self):
        from contacts.exporters import contact_to_vcard

        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            job_title="Engineer",
        )
        payload = contact_to_vcard(contact)
        self.assertIn("TITLE:Engineer", payload)
