from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact


class AuthViewTests(TestCase):
    def test_signup_creates_user(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "ada",
                "email": "ada@example.com",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
            },
        )

        self.assertRedirects(response, reverse("contacts:dashboard"))
        self.assertTrue(User.objects.filter(username="ada").exists())
        self.assertEqual(User.objects.get(username="ada").email, "ada@example.com")

    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user("existing", email="ada@example.com", password="pass")
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newada",
                "email": "Ada@Example.com",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email already exists")
        self.assertFalse(User.objects.filter(username="newada").exists())

    def test_password_reset_form_renders(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset password")

    def test_login_redirects_authenticated_user_from_dashboard(self):
        user = User.objects.create_user("ada", password="pass")
        self.client.force_login(user)

        response = self.client.get(reverse("contacts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_logout_clears_bulk_selection(self):
        user = User.objects.create_user("ada", password="pass")
        contact = Contact.objects.create(owner=user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("selected_contact_ids", self.client.session)

    def test_login_clears_selection_from_prior_user(self):
        user_a = User.objects.create_user("ada", password="pass")
        user_b = User.objects.create_user("bob", password="pass")
        session = self.client.session
        session["selected_contact_ids"] = ["1"]
        session["selected_contact_user_id"] = str(user_a.pk)
        session.save()

        self.client.post(reverse("login"), {"username": "bob", "password": "pass"})

        self.assertNotIn("selected_contact_ids", self.client.session)
        self.assertEqual(self.client.session["selected_contact_user_id"], str(user_b.pk))

    def test_logout_clears_import_errors(self):
        user = User.objects.create_user("ada", password="pass")
        session = self.client.session
        session["last_import_errors"] = [{"row_number": 2, "data": {}, "errors": {}}]
        session["last_import_errors_user_id"] = str(user.pk)
        session.save()
        self.client.force_login(user)

        self.client.post(reverse("logout"))

        self.assertNotIn("last_import_errors", self.client.session)

    def test_login_clears_import_errors_from_prior_user(self):
        user_a = User.objects.create_user("ada", password="pass")
        user_b = User.objects.create_user("bob", password="pass")
        session = self.client.session
        session["last_import_errors"] = [{"row_number": 2, "data": {}, "errors": {}}]
        session["last_import_errors_user_id"] = str(user_a.pk)
        session.save()

        self.client.post(reverse("login"), {"username": "bob", "password": "pass"})

        self.assertNotIn("last_import_errors", self.client.session)

    def test_cross_user_cannot_download_import_error_report(self):
        user_a = User.objects.create_user("ada", password="pass")
        user_b = User.objects.create_user("bob", password="pass")
        session = self.client.session
        session["last_import_errors"] = [{"row_number": 2, "data": {}, "errors": {}}]
        session["last_import_errors_user_id"] = str(user_a.pk)
        session.save()
        self.client.force_login(user_b)

        response = self.client.get(reverse("contacts:csv_error_report"))

        self.assertEqual(response.status_code, 404)
