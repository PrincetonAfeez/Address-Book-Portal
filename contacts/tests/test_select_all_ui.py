""" Test select all UI for the contacts app """

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from contacts.models import Contact


class SelectAllUITests(TestCase):
    """Guard the rendered select-all control — not just POST payloads."""

    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)
        self.factory = RequestFactory()

    def test_select_all_partial_has_no_inline_click_handler(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        request = self.factory.get("/contacts/")
        request.user = self.user
        html = render_to_string(
            "contacts/partials/_select_all_form.html",
            {
                "contacts": [contact],
                "mode": "active",
                "page_all_selected": False,
                "request": request,
            },
        )
        self.assertIn('id="select-all-form"', html)
        self.assertNotIn("hx-on:click", html)
        self.assertIn('name="selected" value="true"', html)
        self.assertNotIn('name="selected" value="false"', html)

    def test_select_all_partial_checked_state_requests_deselect(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        request = self.factory.get("/contacts/")
        request.user = self.user
        html = render_to_string(
            "contacts/partials/_select_all_form.html",
            {
                "contacts": [contact],
                "mode": "active",
                "page_all_selected": True,
                "request": request,
            },
        )
        self.assertIn('name="selected" value="false"', html)
        self.assertIn("checked", html)

    def test_contact_list_renders_select_all_without_inverted_handler(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        select_all = content.split('id="select-all-form"', 1)[1].split("</div>", 1)[0]
        self.assertIn('name="selected" value="true"', select_all)
        self.assertNotIn("hx-on:click", select_all)

    def test_contact_list_select_all_checked_when_page_fully_selected(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session["selected_contact_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.get(reverse("contacts:list"))
        self.assertContains(response, 'name="selected" value="false"')
        content = response.content.decode()
        select_all = content.split('id="select-all-form"', 1)[1].split("</div>", 1)[0]
        self.assertIn('aria-label="Select all on page"', select_all)
        self.assertIn("checked", select_all)
        self.assertNotIn("hx-on:click", select_all)
