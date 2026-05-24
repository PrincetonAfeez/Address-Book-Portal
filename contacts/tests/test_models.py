""" Test models for the contacts app """

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, Group, Tag


class ContactModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def test_manager_scopes_contacts_by_owner(self):
        mine = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        Contact.objects.create(owner=self.other, first_name="Grace", last_name="Hopper")

        self.assertEqual(list(Contact.objects.for_user(self.user)), [mine])

    def test_soft_delete_moves_contact_to_archive(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")

        contact.soft_delete()

        self.assertFalse(Contact.objects.for_user(self.user).active().exists())
        self.assertEqual(Contact.objects.for_user(self.user).archived().get(), contact)

    def test_group_and_tag_relationships_are_user_owned(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        group = Group.objects.create(owner=self.user, name="Friends")
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#10b981")

        group.contacts.add(contact)
        tag.contacts.add(contact)

        self.assertEqual(contact.groups.get(), group)
        self.assertEqual(contact.tags.get(), tag)

    def test_group_rejects_cross_owner_contacts(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        group = Group.objects.create(owner=self.user, name="Friends")

        with self.assertRaises(ValidationError):
            group.contacts.add(contact)

    def test_save_normalizes_phone(self):
        contact = Contact(owner=self.user, first_name="Ada", phone="(415) 555-2671")
        contact.save()

        self.assertEqual(contact.phone, "+14155552671")

    def test_group_name_unique_case_insensitive(self):
        Group.objects.create(owner=self.user, name="Friends")
        with self.assertRaises(ValidationError):
            Group.objects.create(owner=self.user, name="friends")

    def test_group_name_strips_whitespace_on_save(self):
        group = Group.objects.create(owner=self.user, name="  VIP  ")
        self.assertEqual(group.name, "VIP")

    def test_group_whitespace_duplicate_collapses_to_unique_violation(self):
        Group.objects.create(owner=self.user, name="VIP")
        with self.assertRaises(ValidationError):
            Group.objects.create(owner=self.user, name=" VIP ")

    def test_contact_clean_binds_invalid_phone_to_field(self):
        contact = Contact(owner=self.user, first_name="Ada", phone="not-a-phone")
        with self.assertRaises(ValidationError) as ctx:
            contact.full_clean()
        self.assertIn("phone", ctx.exception.message_dict)

    def test_create_validated_persists_contact(self):
        contact = Contact.create_validated(owner=self.user, first_name="Ada", phone="(415) 555-2671")
        self.assertEqual(contact.phone, "+14155552671")
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())
