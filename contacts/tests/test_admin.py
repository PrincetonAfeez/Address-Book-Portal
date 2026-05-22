from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase

from contacts.admin import ContactAdmin, GroupAdmin, TagAdmin
from contacts.models import Contact, Group, Tag


class AdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.site = AdminSite()

    def test_contact_admin_display_name(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        admin = ContactAdmin(Contact, self.site)
        self.assertIn("display_name", admin.list_display)

    def test_group_admin_contact_count(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        group.contacts.add(contact)
        admin = GroupAdmin(Group, self.site)
        self.assertEqual(admin.contact_count(group), 1)

    def test_tag_admin_contact_count(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        tag.contacts.add(contact)
        admin = TagAdmin(Tag, self.site)
        self.assertEqual(admin.contact_count(tag), 1)
