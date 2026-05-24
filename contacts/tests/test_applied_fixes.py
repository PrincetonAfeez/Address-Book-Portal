""" Test applied fixes for the contacts app """

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.exporters import contact_to_vcard, csv_contact_rows
from contacts.models import Contact, Email, Group, Phone, Tag


class AppliedAuditFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_csv_export_uses_display_phone_from_related_row(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        Phone.objects.create(contact=contact, number="+14155552671", label=Phone.MOBILE)
        rows = list(csv_contact_rows(Contact.objects.for_user(self.user)))
        data_row = rows[-1]
        self.assertIn("+14155552671", data_row)

    def test_vcard_includes_scalar_and_related_email(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            email="primary@example.com",
        )
        Email.objects.create(contact=contact, address="work@example.com", label=Email.WORK)
        payload = contact_to_vcard(contact)
        self.assertIn("primary@example.com", payload)
        self.assertIn("work@example.com", payload)

    def test_vcard_includes_uid_and_rev(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        payload = contact_to_vcard(contact)
        self.assertIn(f"UID:{contact.uuid}@address-book-portal", payload)
        self.assertIn("REV:", payload)

    def test_group_edit_updates_name(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        response = self.client.post(
            reverse("contacts:group_edit", args=[group.pk]),
            {"name": "Close Friends"},
        )
        self.assertRedirects(response, reverse("contacts:organization"))
        group.refresh_from_db()
        self.assertEqual(group.name, "Close Friends")

    def test_tag_edit_updates_name_and_color(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        response = self.client.post(
            reverse("contacts:tag_edit", args=[tag.pk]),
            {"name": "Priority", "color": "#10b981"},
        )
        self.assertRedirects(response, reverse("contacts:organization"))
        tag.refresh_from_db()
        self.assertEqual(tag.name, "Priority")
        self.assertEqual(tag.color, "#10b981")

    def test_archive_contact_can_be_purged(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(reverse("contacts:purge", args=[contact.pk]))
        self.assertRedirects(response, reverse("contacts:list"))
        self.assertFalse(Contact.objects.filter(pk=contact.pk).exists())

    def test_purge_rejects_active_contact(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(reverse("contacts:purge", args=[contact.pk]))
        self.assertRedirects(response, reverse("contacts:detail", args=[contact.pk]))
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_detail_page_shows_archive_and_favorite_actions(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:detail", args=[contact.pk]))
        self.assertContains(response, "Favorite")
        self.assertContains(response, "Archive")

    def test_soft_delete_clears_favorite_flag(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            is_favorite=True,
        )
        contact.soft_delete()
        contact.refresh_from_db()
        self.assertFalse(contact.is_favorite)
        self.assertTrue(contact.is_archived)

    def test_contact_form_rejects_blank_first_name(self):
        response = self.client.post(
            reverse("contacts:create"),
            {"first_name": "   ", "phone": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(first_name="").exists())

    def test_csv_import_warns_on_unknown_columns(self):
        csv_body = b"First Name,Last Name,Favorite\nAda,Lovelace,Yes\n"
        response = self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertContains(response, "Ignored unrecognized columns")

    def test_export_selected_only_when_requested(self):
        selected = Contact.objects.create(owner=self.user, first_name="Selected")
        Contact.objects.create(owner=self.user, first_name="Other")
        session = self.client.session
        session["selected_contact_ids"] = [str(selected.pk)]
        session["selected_contact_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.get(reverse("contacts:csv_export"), {"selected": "1"})
        content = b"".join(response.streaming_content)
        self.assertIn(b"Selected", content)
        self.assertNotIn(b"Other", content)

    def test_bulk_restore_from_archive(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session["selected_contact_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "restore", "list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertFalse(contact.is_archived)
