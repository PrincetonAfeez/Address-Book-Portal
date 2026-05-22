from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, Group, Tag


class ContactActionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_signup_get_renders_form(self):
        self.client.logout()
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "username")

    def test_contact_delete_full_page_redirects_to_list(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(reverse("contacts:delete", args=[contact.pk]))
        self.assertRedirects(response, reverse("contacts:list"))
        contact.refresh_from_db()
        self.assertTrue(contact.is_archived)

    def test_contact_delete_from_favorites_redirects(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_favorite=True)
        response = self.client.post(
            reverse("contacts:delete", args=[contact.pk]),
            {"list_mode": "favorites"},
        )
        self.assertRedirects(response, reverse("contacts:favorites"))

    def test_contact_delete_htmx_from_archive_refreshes_rows(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(
            reverse("contacts:delete", args=[contact.pk]),
            {"list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertTrue(contact.is_archived)

    def test_contact_restore_full_page_redirects(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(reverse("contacts:restore", args=[contact.pk]))
        self.assertRedirects(response, reverse("contacts:archive"))
        contact.refresh_from_db()
        self.assertFalse(contact.is_archived)

    def test_contact_toggle_favorite_htmx_on_list(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(
            reverse("contacts:favorite", args=[contact.pk]),
            {"list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertTrue(contact.is_favorite)

    def test_contact_delete_from_archive_redirects(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(
            reverse("contacts:delete", args=[contact.pk]),
            {"list_mode": "archive"},
        )
        self.assertRedirects(response, reverse("contacts:archive"))

    def test_contact_toggle_favorite_full_page_from_active_list(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(
            reverse("contacts:favorite", args=[contact.pk]),
            {"list_mode": "active"},
        )
        self.assertRedirects(response, reverse("contacts:list"))
        contact.refresh_from_db()
        self.assertTrue(contact.is_favorite)

    def test_contact_toggle_favorite_full_page_from_favorites(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_favorite=True)
        response = self.client.post(
            reverse("contacts:favorite", args=[contact.pk]),
            {"list_mode": "favorites"},
        )
        self.assertRedirects(response, reverse("contacts:favorites"))
        contact.refresh_from_db()
        self.assertFalse(contact.is_favorite)

    def test_contact_update_full_page(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", phone="+14155552671")
        response = self.client.post(
            reverse("contacts:edit", args=[contact.pk]),
            {"first_name": "Augusta", "last_name": "Ada", "phone": "+14155552671"},
        )
        self.assertRedirects(response, contact.get_absolute_url())
        contact.refresh_from_db()
        self.assertEqual(contact.first_name, "Augusta")

    def test_contact_update_get_full_page(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:edit", args=[contact.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada")

    def test_contact_update_invalid_htmx_retargets_modal(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(
            reverse("contacts:edit", args=[contact.pk]),
            {"first_name": "", "phone": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Retarget"], "#modal-root")
        self.assertEqual(response["HX-Reswap"], "innerHTML")

    def test_contact_create_invalid_htmx_retargets_modal(self):
        response = self.client.post(
            reverse("contacts:create"),
            {"first_name": "", "phone": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Retarget"], "#modal-root")

    def test_selection_toggle_adds_contact(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(
            reverse("contacts:selection_toggle"),
            {"contact_id": str(contact.pk), "selected": "true", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(contact.pk), self.client.session["selected_contact_ids"])

    def test_selection_toggle_removes_contact(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:selection_toggle"),
            {"contact_id": str(contact.pk), "selected": "false", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["selected_contact_ids"], [])

    def test_selection_toggle_without_list_mode_returns_bar(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.post(
            reverse("contacts:selection_toggle"),
            {"contact_id": str(contact.pk), "selected": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "selected")

    def test_selection_clear_active(self):
        session = self.client.session
        session["selected_contact_ids"] = ["1"]
        session.save()
        response = self.client.post(
            reverse("contacts:selection_clear"),
            {"list_mode": "active"},
        )
        self.assertRedirects(response, reverse("contacts:list"))
        self.assertEqual(self.client.session["selected_contact_ids"], [])

    def test_selection_clear_archive_htmx(self):
        Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(
            reverse("contacts:selection_clear"),
            {"list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_selection_clear_archive_redirect(self):
        response = self.client.post(
            reverse("contacts:selection_clear"),
            {"list_mode": "archive"},
        )
        self.assertRedirects(response, reverse("contacts:archive"))

    def test_selection_clear_favorites_redirect(self):
        response = self.client.post(
            reverse("contacts:selection_clear"),
            {"list_mode": "favorites"},
        )
        self.assertRedirects(response, reverse("contacts:favorites"))

    def test_bulk_action_redirects_active_list_without_htmx(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "archive", "list_mode": "active"},
        )
        self.assertRedirects(response, reverse("contacts:list"))

    def test_selection_page_select_all_on_page(self):
        c1 = Contact.objects.create(owner=self.user, first_name="One")
        c2 = Contact.objects.create(owner=self.user, first_name="Two")
        response = self.client.post(
            reverse("contacts:selection_page"),
            {
                "selected": "true",
                "contact_ids": [str(c1.pk), str(c2.pk)],
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(self.client.session["selected_contact_ids"]),
            {str(c1.pk), str(c2.pk)},
        )

    def test_selection_page_deselect_all_on_page(self):
        c1 = Contact.objects.create(owner=self.user, first_name="One")
        c2 = Contact.objects.create(owner=self.user, first_name="Two")
        session = self.client.session
        session["selected_contact_ids"] = [str(c1.pk), str(c2.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:selection_page"),
            {
                "selected": "false",
                "contact_ids": [str(c1.pk)],
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["selected_contact_ids"], [str(c2.pk)])

    def test_bulk_add_group(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_group", "group": str(group.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(contact, group.contacts.all())

    def test_bulk_add_tag(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_tag", "tag": str(tag.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(contact, tag.contacts.all())

    def test_bulk_remove_tag(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        tag.contacts.add(contact)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "remove_tag", "tag": str(tag.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(contact, tag.contacts.all())

    def test_bulk_action_invalid_shows_error(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_group", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_bulk_action_redirects_archive_without_htmx(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "delete", "list_mode": "archive"},
        )
        self.assertRedirects(response, reverse("contacts:archive"))

    def test_bulk_action_redirects_favorites_without_htmx(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_favorite=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "archive", "list_mode": "favorites"},
        )
        self.assertRedirects(response, reverse("contacts:favorites"))

    def test_csv_import_view_success(self):
        csv_body = b"First Name,Last Name,Email\nAda,Lovelace,ada@example.com\n"
        response = self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 contacts imported")

    def test_csv_import_view_reports_failures(self):
        csv_body = b"First Name,Last Name\n,Missing\n"
        response = self.client.post(
            reverse("contacts:csv_import"),
            {"file": SimpleUploadedFile("contacts.csv", csv_body, content_type="text/csv")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "rows failed")

    def test_vcard_bulk_export(self):
        Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        response = self.client.get(reverse("contacts:vcard_bulk"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/vcard")
        self.assertIn(b"BEGIN:VCARD", b"".join(response.streaming_content))
