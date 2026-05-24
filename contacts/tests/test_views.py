""" Test views for the contacts app """

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, Group, Tag


class ContactViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def test_auth_is_required_for_contact_list(self):
        response = self.client.get(reverse("contacts:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_cross_user_detail_returns_404(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:detail", args=[contact.pk]))

        self.assertEqual(response.status_code, 404)

    def test_htmx_search_returns_rows_partial(self):
        Contact.objects.create(owner=self.user, first_name="Ada", company="Analytical Engines")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("contacts:list"),
            {"q": "Analytical"},
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, "Ada")
        self.assertNotContains(response, "<table")

    def test_htmx_search_updates_pagination_and_select_all_oob(self):
        for index in range(30):
            Contact.objects.create(owner=self.user, first_name=f"Person{index}", company="Acme")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("contacts:list"),
            {"q": "Person2"},
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, 'id="contact-list-pagination"')
        self.assertContains(response, 'id="select-all-form"')
        self.assertContains(response, "hx-swap-oob")
        self.assertContains(response, "q=Person2")

    def test_create_contact_via_htmx_on_list(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone": "(415) 555-2671",
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(first_name="Ada").exists())
        self.assertContains(response, "Ada Lovelace")

    def test_create_contact_via_htmx_from_archive_refreshes_active_list(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone": "(415) 555-2671",
                "list_mode": "archive",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(first_name="Ada", is_archived=False).exists())
        self.assertContains(response, "Ada Lovelace")

    def test_duplicate_group_name_shows_form_error(self):
        Group.objects.create(owner=self.user, name="Friends")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:organization"),
            {"kind": "group", "group-name": "Friends"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a group")

    def test_selection_count_drops_deleted_contacts(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk), "9999"]
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"))

        self.assertContains(response, "1 selected")
        self.assertEqual(self.client.session["selected_contact_ids"], [str(contact.pk)])

    def test_create_contact_via_htmx_from_favorites_refreshes_list(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone": "(415) 555-2671",
                "is_favorite": "on",
                "list_mode": "favorites",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(first_name="Ada", is_favorite=True).exists())
        self.assertContains(response, 'id="contact-')
        self.assertContains(response, "Ada Lovelace")

    def test_create_non_favorite_via_htmx_from_favorites_refreshes_active_list(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {
                "first_name": "Bob",
                "last_name": "Plain",
                "phone": "(415) 555-2671",
                "list_mode": "favorites",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(first_name="Bob", is_favorite=False).exists())
        self.assertContains(response, "Bob Plain")

    def test_modal_create_form_posts_to_create_url(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("contacts:create"),
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, 'hx-post="/contacts/new/"')
        self.assertNotContains(response, "contact-table-body")

    def test_edit_from_detail_via_htmx_redirects(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:edit", args=[contact.pk]),
            {"first_name": "Ada", "last_name": "Byron", "phone": "(415) 555-2671"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], contact.get_absolute_url())
        contact.refresh_from_db()
        self.assertEqual(contact.last_name, "Byron")

    def test_edit_from_list_via_htmx_clears_modal(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:edit", args=[contact.pk]),
            {
                "first_name": "Ada",
                "last_name": "Byron",
                "phone": "(415) 555-2671",
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="modal-root" hx-swap-oob="innerHTML"')
        contact.refresh_from_db()
        self.assertEqual(contact.last_name, "Byron")

    def test_view_switch_preserves_group_filter(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"), {"group": group.pk})

        self.assertContains(response, f"/contacts/favorites/?group={group.pk}")
        self.assertContains(response, f"/contacts/archive/?group={group.pk}")

    def test_bulk_action_on_archive_only_affects_archived_selection(self):
        active = Contact.objects.create(owner=self.user, first_name="Active")
        archived = Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(active.pk), str(archived.pk)]
        session.save()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "delete", "list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(pk=archived.pk).exists())
        self.assertTrue(Contact.objects.filter(pk=active.pk).exists())

    def test_create_contact_via_htmx_from_dashboard_redirects(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {"first_name": "Ada", "last_name": "Lovelace", "phone": "(415) 555-2671"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 204)
        self.assertIn("/contacts/", response["HX-Redirect"])

    def test_archive_restore_keeps_archive_mode(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:restore", args=[contact.pk]),
            {"list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No archived contacts")
        contact.refresh_from_db()
        self.assertFalse(contact.is_archived)

    def test_full_page_create_redirects_to_detail(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:create"),
            {"first_name": "Ada", "last_name": "Lovelace", "phone": "(415) 555-2671"},
        )

        contact = Contact.objects.get(first_name="Ada")
        self.assertRedirects(response, contact.get_absolute_url())

    def test_csv_error_report_404_without_session(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:csv_error_report"))

        self.assertEqual(response.status_code, 404)

    def test_bulk_archive_soft_deletes(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "archive", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        contact.refresh_from_db()
        self.assertTrue(contact.is_archived)

    def test_bulk_delete_permanently_removes_contacts(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "delete", "list_mode": "archive"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(pk=contact.pk).exists())

    def test_contact_list_shows_sort_indicator(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"), {"sort": "name", "dir": "asc"})

        self.assertContains(response, "Name ▲")

    def test_contact_list_paginates(self):
        for index in range(30):
            Contact.objects.create(owner=self.user, first_name=f"Person{index}")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"))

        self.assertContains(response, "Page 1 of 2")

    def test_favorites_list_shows_only_favorites(self):
        Contact.objects.create(owner=self.user, first_name="Starred", is_favorite=True)
        Contact.objects.create(owner=self.user, first_name="Plain")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:favorites"))

        self.assertContains(response, "Starred")
        self.assertNotContains(response, ">Plain<")

    def test_group_filter_limits_results(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        in_group = Contact.objects.create(owner=self.user, first_name="In")
        Contact.objects.create(owner=self.user, first_name="Out")
        group.contacts.add(in_group)
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"), {"group": group.pk})

        self.assertContains(response, "In")
        self.assertNotContains(response, ">Out<")

    def test_tag_filter_limits_results(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        tagged = Contact.objects.create(owner=self.user, first_name="Tagged")
        Contact.objects.create(owner=self.user, first_name="Plain")
        tagged.tags.add(tag)
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:list"), {"tag": tag.pk})

        self.assertContains(response, "Tagged")
        self.assertNotContains(response, ">Plain<")

    def test_htmx_empty_archive_shows_mode_specific_subtitle(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("contacts:archive"),
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "No archived contacts")
        self.assertNotContains(response, "No contacts yet — add your first one")

    def test_selection_count_is_scoped_to_current_view(self):
        active = Contact.objects.create(owner=self.user, first_name="Active")
        archived = Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        session = self.client.session
        session["selected_contact_ids"] = [str(active.pk), str(archived.pk)]
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:archive"))

        self.assertContains(response, "1 selected")
        self.assertNotContains(response, "2 selected")

    def test_archive_list_shows_archived_contact(self):
        Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:archive"))

        self.assertContains(response, "Archived")

    def test_csv_import_page_requires_login(self):
        response = self.client.get(reverse("contacts:csv_import"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_contact_detail_shows_archived_badge(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            is_archived=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:detail", args=[contact.pk]))

        self.assertContains(response, "Archived")
