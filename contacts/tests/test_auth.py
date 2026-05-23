from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


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
