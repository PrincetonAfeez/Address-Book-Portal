from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from contacts.forms import BulkActionForm, CSVImportForm, ContactForm, GroupForm, SignupForm, TagForm
from contacts.models import Contact, Email, Group, Phone, Tag


class FormsExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_signup_form_valid(self):
        form = SignupForm(
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_signup_form_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user("existing", email="Ada@Example.com", password="pass")
        form = SignupForm(
            data={
                "username": "newuser",
                "email": "ada@example.com",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_group_form_rejects_empty_name(self):
        form = GroupForm(data={"name": "   "}, user=self.user, prefix="group")
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_group_form_allows_same_name_on_edit(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        form = GroupForm(data={"name": "friends"}, instance=group, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_tag_form_rejects_invalid_color(self):
        form = TagForm(
            data={"name": "VIP", "color": "red"},
            user=self.user,
            prefix="tag",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("color", form.errors)

    def test_tag_form_rejects_non_hex_digits(self):
        form = TagForm(
            data={"name": "VIP", "color": "#zzzzzz"},
            user=self.user,
            prefix="tag",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("color", form.errors)

    def test_tag_form_rejects_empty_name(self):
        form = TagForm(data={"name": "", "color": "#2563eb"}, user=self.user, prefix="tag")
        self.assertFalse(form.is_valid())

    def test_csv_import_form_rejects_non_csv(self):
        uploaded = SimpleUploadedFile("data.txt", b"a,b", content_type="text/plain")
        form = CSVImportForm(files={"file": uploaded})
        self.assertFalse(form.is_valid())
        self.assertIn("CSV", form.errors["file"][0])

    def test_bulk_action_form_requires_group(self):
        form = BulkActionForm(data={"action": "add_group"}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("group", form.errors)

    def test_bulk_action_form_requires_tag_for_remove(self):
        form = BulkActionForm(data={"action": "remove_tag"}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("tag", form.errors)

    def test_bulk_action_form_archive_mode_choices(self):
        form = BulkActionForm(user=self.user, list_mode="archive")
        actions = [choice[0] for choice in form.fields["action"].choices]
        self.assertNotIn("archive", actions)
        self.assertIn("delete", actions)

    def test_contact_form_sync_primary_records_email(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            email="ada@example.com",
        )
        form = ContactForm(instance=contact)
        form.sync_primary_records(contact)
        self.assertEqual(contact.emails.get().address, "ada@example.com")
        self.assertEqual(contact.emails.get().label, Email.OTHER)

    def test_contact_form_clears_phone_sync(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", phone="+14155552671")
        Phone.objects.create(contact=contact, number="+14155552671", label=Phone.MOBILE)
        form = ContactForm(
            data={
                "first_name": "Ada",
                "last_name": "",
                "email": "",
                "phone": "",
                "company": "",
                "job_title": "",
                "birthday": "",
                "notes": "",
            },
            instance=contact,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        form.sync_primary_records(saved)
        self.assertFalse(saved.phones.exists())

    def test_contact_form_clean_phone_empty(self):
        form = ContactForm(data={"first_name": "Ada", "phone": ""})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "")
