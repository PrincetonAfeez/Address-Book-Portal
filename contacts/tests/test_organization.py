""" Test organization for the contacts app """

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contacts.models import Group, Tag


class OrganizationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_create_tag(self):
        response = self.client.post(
            reverse("contacts:organization"),
            {"kind": "tag", "tag-name": "VIP", "tag-color": "#2563eb"},
        )

        self.assertRedirects(response, reverse("contacts:organization"))
        self.assertTrue(Tag.objects.filter(name="VIP", owner=self.user).exists())

    def test_create_group(self):
        response = self.client.post(
            reverse("contacts:organization"),
            {"kind": "group", "group-name": "Friends"},
        )

        self.assertRedirects(response, reverse("contacts:organization"))
        self.assertTrue(Group.objects.filter(name="Friends", owner=self.user).exists())

    def test_group_delete_removes_group(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        response = self.client.post(reverse("contacts:group_delete", args=[group.pk]))
        self.assertRedirects(response, reverse("contacts:organization"))
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())

    def test_tag_delete_removes_tag(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        response = self.client.post(reverse("contacts:tag_delete", args=[tag.pk]))
        self.assertRedirects(response, reverse("contacts:organization"))
        self.assertFalse(Tag.objects.filter(pk=tag.pk).exists())

    def test_duplicate_tag_name_shows_form_error(self):
        Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")

        response = self.client.post(
            reverse("contacts:organization"),
            {"kind": "tag", "tag-name": "VIP", "tag-color": "#10b981"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a tag")

    def test_group_delete_requires_login(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        self.client.logout()

        response = self.client.post(reverse("contacts:group_delete", args=[group.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_organization_lists_existing_groups(self):
        Group.objects.create(owner=self.user, name="Friends")

        response = self.client.get(reverse("contacts:organization"))

        self.assertContains(response, "Friends")
