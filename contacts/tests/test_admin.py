from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from contacts.admin import ContactAdmin, GroupAdmin, TagAdmin
from contacts.models import Contact, Group, Tag


class AdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("bob", password="pass")
        self.site = AdminSite()
        self.factory = RequestFactory()

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

    def test_contact_admin_scopes_queryset_for_staff(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.other, first_name="Bob")
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/contacts/contact/")
        request.user = self.user
        admin = ContactAdmin(Contact, self.site)
        self.assertEqual(admin.get_queryset(request).count(), 1)
        self.assertEqual(admin.get_queryset(request).get().first_name, "Ada")

    def test_contact_admin_shows_all_for_superuser(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.other, first_name="Bob")
        request = self.factory.get("/admin/contacts/contact/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = ContactAdmin(Contact, self.site)
        self.assertEqual(admin.get_queryset(request).count(), 2)

    def test_group_admin_hides_owner_field_for_staff(self):
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/contacts/group/add/")
        request.user = self.user
        admin = GroupAdmin(Group, self.site)
        self.assertNotIn("owner", admin.get_fields(request))
