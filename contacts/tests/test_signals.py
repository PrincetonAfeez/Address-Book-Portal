from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, Group, Tag


class SignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def test_tag_rejects_cross_owner_contacts(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        with self.assertRaises(ValidationError):
            tag.contacts.add(contact)

    def test_group_rejects_cross_owner_contacts(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        group = Group.objects.create(owner=self.user, name="Friends")
        with self.assertRaises(ValidationError):
            group.contacts.add(contact)

    def test_group_rejects_cross_owner_via_reverse_relation(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        other_group = Group.objects.create(owner=self.other, name="Friends")
        with self.assertRaises(ValidationError):
            contact.groups.add(other_group)

    def test_tag_rejects_cross_owner_via_reverse_relation(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        other_tag = Tag.objects.create(owner=self.other, name="VIP", color="#2563eb")
        with self.assertRaises(ValidationError):
            contact.tags.add(other_tag)
