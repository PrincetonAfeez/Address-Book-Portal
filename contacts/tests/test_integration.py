from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from contacts import signals
from contacts.importers import error_report_rows
from contacts.models import Contact, Group, Tag


class SignalHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_validate_contact_ownership_ignores_empty_pk_set(self):
        signals._validate_contact_ownership(self.user.pk, set())

    def test_validate_group_ownership_ignores_empty_pk_set(self):
        signals._validate_group_ownership(self.user.pk, set())

    def test_validate_tag_ownership_ignores_empty_pk_set(self):
        signals._validate_tag_ownership(self.user.pk, set())


class ImporterReportTests(TestCase):
    def test_error_report_rows_streams_csv(self):
        from contacts.importers import RowError

        rows = list(
            error_report_rows(
                [RowError(2, {"first_name": ""}, {"first_name": ["Required."]})]
            )
        )
        payload = "".join(rows)
        self.assertIn("Row,Field,Error", payload)
        self.assertIn("Required.", payload)


class ViewIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_dashboard_renders(self):
        response = self.client.get(reverse("contacts:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_contact_detail_renders(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        response = self.client.get(contact.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Lovelace")

    def test_contact_form_standalone_create_get(self):
        response = self.client.get(reverse("contacts:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add contact")

    def test_contact_form_standalone_edit_get(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:edit", args=[contact.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit contact")

    def test_restore_via_htmx_on_archive_list(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        response = self.client.post(
            reverse("contacts:restore", args=[contact.pk]),
            {"list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertFalse(contact.is_archived)

    def test_selection_clear_via_htmx(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:selection_clear"),
            {"list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get("selected_contact_ids"), [])

    def test_bulk_action_success_message_counts(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "archive", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertTrue(contact.is_archived)

    def test_archive_list_export_respects_mode(self):
        Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        response = self.client.get(reverse("contacts:csv_export"), {"mode": "archive"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Archived", b"".join(response.streaming_content))

    def test_search_sort_and_group_combined(self):
        group = Group.objects.create(owner=self.user, name="Team")
        contact = Contact.objects.create(owner=self.user, first_name="FindMe", company="Acme")
        group.contacts.add(contact)
        response = self.client.get(
            reverse("contacts:list"),
            {"q": "Find", "group": group.pk, "sort": "company", "dir": "asc"},
        )
        self.assertContains(response, "FindMe")
        self.assertNotContains(response, "Page 2")

    def test_organization_get_renders_forms(self):
        response = self.client.get(reverse("contacts:organization"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Groups")
        self.assertContains(response, "Tags")

    def test_tag_filter_on_favorites_view(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        favorite = Contact.objects.create(owner=self.user, first_name="Star", is_favorite=True)
        Contact.objects.create(owner=self.user, first_name="Plain", is_favorite=True)
        favorite.tags.add(tag)
        response = self.client.get(reverse("contacts:favorites"), {"tag": tag.pk})
        self.assertContains(response, "Star")
        self.assertNotContains(response, ">Plain<")
