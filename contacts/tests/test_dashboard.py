from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, Group, Tag


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_dashboard_renders_metrics(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        Group.objects.create(owner=self.user, name="Friends")
        Tag.objects.create(owner=self.user, name="VIP", color="#10b981")
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contacts")
        self.assertContains(response, ">1<", html=False)

    def test_dashboard_lists_upcoming_birthday(self):
        today = date.today()
        upcoming = today + timedelta(days=10)
        Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            birthday=upcoming.replace(year=2000),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("contacts:dashboard"))

        self.assertContains(response, "Upcoming birthdays")
        self.assertContains(response, "Ada")
