from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, Tag


class SignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def test_tag_rejects_cross_owner_contacts(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        with self.assertRaises(ValidationError):
            tag.contacts.add(contact)
