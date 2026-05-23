from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, Tag


class AuditFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")
        self.client.force_login(self.user)

    def test_cross_user_edit_returns_403(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        response = self.client.post(
            reverse("contacts:edit", args=[contact.pk]),
            {"first_name": "Hacked", "phone": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_cross_user_delete_returns_403(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        response = self.client.post(reverse("contacts:delete", args=[contact.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cross_user_vcard_returns_403(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        response = self.client.get(reverse("contacts:vcard_one", args=[contact.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cross_user_restore_returns_403(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace", is_archived=True)
        response = self.client.post(reverse("contacts:restore", args=[contact.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cross_user_favorite_toggle_returns_403(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        response = self.client.post(reverse("contacts:favorite", args=[contact.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cross_user_group_delete_returns_403(self):
        from contacts.models import Group

        group = Group.objects.create(owner=self.other, name="Theirs")
        response = self.client.post(reverse("contacts:group_delete", args=[group.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cross_user_tag_delete_returns_403(self):
        tag = Tag.objects.create(owner=self.other, name="Theirs", color="#2563eb")
        response = self.client.post(reverse("contacts:tag_delete", args=[tag.pk]))
        self.assertEqual(response.status_code, 403)

    def test_csv_import_page_warns_about_primary_fields_only(self):
        response = self.client.get(reverse("contacts:csv_import"))
        self.assertContains(response, "Primary fields only")

    def test_signup_redirects_authenticated_user(self):
        response = self.client.get(reverse("signup"))
        self.assertRedirects(response, reverse("contacts:dashboard"))

    def test_favorites_list_includes_archived_favorites(self):
        Contact.objects.create(
            owner=self.user,
            first_name="ArchivedStar",
            is_favorite=True,
            is_archived=True,
        )
        response = self.client.get(reverse("contacts:favorites"))
        self.assertContains(response, "ArchivedStar")

    def test_csv_import_clears_previous_error_session_on_new_upload(self):
        session = self.client.session
        session["last_import_errors"] = [{"row_number": 2, "data": {}, "errors": {}}]
        session.save()
        csv_body = b"First Name,Last Name\nAda,Lovelace\n"
        self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertNotIn("last_import_errors", self.client.session)

    def test_csv_import_renders_row_level_error_message(self):
        csv_body = b"First Name,Last Name\nAda,Lovelace,Extra\n"
        response = self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertContains(response, "Too many columns")

    def test_bulk_action_warns_when_selection_empty_for_mode(self):
        contact = Contact.objects.create(owner=self.user, first_name="Active")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "delete", "list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_selection_toggle_preserves_page_query(self):
        for index in range(30):
            Contact.objects.create(owner=self.user, first_name=f"Person{index}")
        contact = Contact.objects.for_user(self.user).order_by("last_name", "first_name")[25]
        response = self.client.post(
            reverse("contacts:selection_toggle") + "?page=2",
            {"contact_id": str(contact.pk), "selected": "true", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")

    def test_contact_save_rejects_invalid_phone(self):
        contact = Contact(owner=self.user, first_name="Ada", phone="invalid-phone")
        with self.assertRaises(ValidationError):
            contact.save()

    def test_tag_name_unique_case_insensitive(self):
        Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        with self.assertRaises(ValidationError):
            Tag.objects.create(owner=self.user, name="vip", color="#10b981")

    def test_csv_error_report_clears_session(self):
        session = self.client.session
        session["last_import_errors"] = [
            {"row_number": 2, "data": {}, "errors": {"first_name": ["Required."]}}
        ]
        session["last_import_errors_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.get(reverse("contacts:csv_error_report"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("last_import_errors", self.client.session)
