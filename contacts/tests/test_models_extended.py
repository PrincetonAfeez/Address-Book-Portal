from io import BytesIO

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import TestCase
from PIL import Image

from contacts.models import Contact, Email, Group, Phone, Tag, contact_photo_path


class ModelExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def test_for_user_returns_none_for_anonymous(self):
        self.assertEqual(Contact.objects.for_user(None).count(), 0)

    def test_get_for_user_or_404_raises_403_for_other_owner(self):
        contact = Contact.objects.create(owner=self.other, first_name="Grace")
        with self.assertRaises(PermissionDenied):
            Contact.objects.get_for_user_or_404(self.user, pk=contact.pk)

    def test_get_for_user_or_404_raises_404_when_missing(self):
        with self.assertRaises(Http404):
            Contact.objects.get_for_user_or_404(self.user, pk=9999)

    def test_contact_str_and_properties(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", last_name="Lovelace")
        self.assertEqual(str(contact), "Ada Lovelace")
        self.assertEqual(contact.initials, "AL")
        self.assertIn(f"/contacts/{contact.pk}/", contact.get_absolute_url())

    def test_contact_initials_fallback(self):
        contact = Contact(owner=self.user, first_name="", last_name="")
        self.assertEqual(contact.initials, "?")

    def test_search_matches_related_phone_and_email(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        Phone.objects.create(contact=contact, number="+14155552671")
        Email.objects.create(contact=contact, address="unique@example.com")
        by_phone = Contact.objects.for_user(self.user).search("5552671")
        by_email = Contact.objects.for_user(self.user).search("unique@")
        self.assertEqual(list(by_phone), [contact])
        self.assertEqual(list(by_email), [contact])

    def test_search_matches_scalar_phone_without_related_row(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            phone="+14155552671",
        )
        results = Contact.objects.for_user(self.user).search("5552671")
        self.assertEqual(list(results), [contact])

    def test_phone_str_and_clean(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        phone = Phone(contact=contact, number="(415) 555-2671")
        phone.save()
        self.assertIn("+14155552671", str(phone))

    def test_email_str(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        email = Email.objects.create(contact=contact, address="ada@example.com", label=Email.WORK)
        self.assertIn("ada@example.com", str(email))

    def test_group_and_tag_str(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        self.assertEqual(str(group), "Friends")
        self.assertEqual(str(tag), "VIP")

    def test_tag_clean_rejects_invalid_color(self):
        tag = Tag(owner=self.user, name="VIP", color="blue")
        with self.assertRaises(ValidationError):
            tag.full_clean()

    def test_tag_clean_rejects_non_hex_digits(self):
        tag = Tag(owner=self.user, name="VIP", color="#zzzzzz")
        with self.assertRaises(ValidationError):
            tag.full_clean()

    def test_contact_photo_path_includes_owner(self):
        contact = Contact(owner=self.user, first_name="Ada")
        path = contact_photo_path(contact, "avatar.JPG")
        self.assertIn(f"user_{self.user.pk}", path)
        self.assertTrue(path.endswith(".jpg"))

    def test_contact_save_resizes_photo(self):
        buffer = BytesIO()
        Image.new("RGB", (1200, 900), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        photo = SimpleUploadedFile("big.jpg", buffer.read(), content_type="image/jpeg")
        contact = Contact(owner=self.user, first_name="Ada", photo=photo)
        contact.save(resize_photo=True)
        with Image.open(contact.photo.path) as image:
            self.assertLessEqual(max(image.size), 800)

    def test_contact_save_rejects_invalid_phone(self):
        contact = Contact(owner=self.user, first_name="Ada", phone="invalid-phone")
        with self.assertRaises(ValidationError):
            contact.save()

    def test_contact_display_email_falls_back_to_related_row(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        Email.objects.create(contact=contact, address="ada@example.com", label=Email.OTHER)
        self.assertEqual(contact.display_email, "ada@example.com")
        self.assertEqual(contact.display_phone, "")

    def test_restore_contact(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", is_archived=True)
        contact.restore()
        self.assertFalse(contact.is_archived)
