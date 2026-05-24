""" Test round two fixes for the contacts app """

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.exporters import contact_to_vcard
from contacts.forms import ContactForm
from contacts.models import Contact, Email, Group, Phone, Tag


class RoundTwoFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_export_selected_empty_returns_header_only(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:csv_export"), {"selected": "1"})
        content = b"".join(response.streaming_content)
        self.assertIn(b"First Name", content)
        self.assertNotIn(b"Ada", content)

    def test_cannot_favorite_archived_contact(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            is_archived=True,
        )
        response = self.client.post(
            reverse("contacts:favorite", args=[contact.pk]),
            {"list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertFalse(contact.is_favorite)

    def test_selection_page_select_all_adds_page_contacts(self):
        for index in range(3):
            Contact.objects.create(owner=self.user, first_name=f"Person{index}")
        ids = list(Contact.objects.for_user(self.user).values_list("pk", flat=True))
        response = self.client.post(
            reverse("contacts:selection_page"),
            {
                "contact_ids": [str(pk) for pk in ids],
                "selected": "true",
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.client.session["selected_contact_ids"]), 3)

    def test_contact_form_assigns_groups_and_tags(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        response = self.client.post(
            reverse("contacts:create"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone": "",
                "email": "",
                "groups": [str(group.pk)],
                "tags": [str(tag.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        contact = Contact.objects.get(first_name="Ada")
        self.assertIn(group, contact.groups.all())
        self.assertIn(tag, contact.tags.all())

    def test_contact_form_rejects_oversized_photo(self):
        large = SimpleUploadedFile("big.jpg", b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        form = ContactForm(
            data={"first_name": "Ada", "phone": "", "email": ""},
            files={"photo": large},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)

    def test_model_rejects_whitespace_first_name(self):
        contact = Contact(owner=self.user, first_name="   ", last_name="Test")
        with self.assertRaises(Exception):
            contact.save()

    def test_vcard_rev_uses_utc_suffix(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        payload = contact_to_vcard(contact)
        self.assertRegex(payload, r"REV:\d{8}T\d{6}Z")

    def test_csv_export_selected_respects_list_filter(self):
        group = Group.objects.create(owner=self.user, name="Team")
        in_group = Contact.objects.create(owner=self.user, first_name="In")
        out_group = Contact.objects.create(owner=self.user, first_name="Out")
        group.contacts.add(in_group)
        session = self.client.session
        session["selected_contact_ids"] = [str(in_group.pk), str(out_group.pk)]
        session["selected_contact_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.get(
            reverse("contacts:csv_export"),
            {"selected": "1", "group": str(group.pk)},
        )
        content = b"".join(response.streaming_content)
        self.assertIn(b"In", content)
        self.assertNotIn(b"Out", content)

    def test_related_only_email_duplicate_warning(self):
        contact = Contact.objects.create(owner=self.user, first_name="Existing")
        Email.objects.create(contact=contact, address="dup@example.com", label=Email.OTHER)
        csv_body = b"First Name,Last Name,Email\nBob,Smith,dup@example.com\n"
        response = self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertContains(response, "duplicate email skipped")
        self.assertFalse(Contact.objects.filter(first_name="Bob").exists())

    def test_group_favorites_queryset_is_noop(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        queryset = Group.objects.for_user(self.user).favorites()
        self.assertEqual(list(queryset), [group])

    def test_selection_page_non_htmx_redirects_to_list(self):
        response = self.client.post(
            reverse("contacts:selection_page"),
            {"contact_ids": [], "selected": "true", "list_mode": "active"},
        )
        self.assertRedirects(response, reverse("contacts:list"))

    def test_bulk_delete_singular_success_message(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session["selected_contact_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "delete", "list_mode": "archive"},
        )
        self.assertRedirects(response, reverse("contacts:archive"))
        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), "1 contact permanently deleted.")

    def test_archived_contact_row_shows_restore_not_archive(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            is_favorite=True,
            is_archived=True,
        )
        response = self.client.get(reverse("contacts:archive"))
        self.assertContains(response, reverse("contacts:restore", args=[contact.pk]))
        self.assertNotContains(response, reverse("contacts:delete", args=[contact.pk]))
