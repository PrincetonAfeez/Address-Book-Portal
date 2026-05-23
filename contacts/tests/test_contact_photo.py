from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from contacts.models import Contact


class ContactPhotoViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("grace", password="pass")

    def _photo_file(self):
        buffer = BytesIO()
        Image.new("RGB", (40, 40), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("photo.jpg", buffer.read(), content_type="image/jpeg")

    def _contact_with_photo(self, owner):
        contact = Contact.objects.create(owner=owner, first_name="Ada")
        contact.photo = self._photo_file()
        contact.save(resize_photo=False)
        return contact

    def test_photo_url_points_to_authenticated_view(self):
        contact = self._contact_with_photo(self.user)
        self.assertEqual(contact.photo_url, reverse("contacts:photo", args=[contact.pk]))

    def test_contact_photo_requires_login(self):
        contact = self._contact_with_photo(self.user)
        response = self.client.get(reverse("contacts:photo", args=[contact.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_contact_photo_cross_user_returns_403(self):
        contact = self._contact_with_photo(self.other)
        self.client.force_login(self.user)
        response = self.client.get(reverse("contacts:photo", args=[contact.pk]))
        self.assertEqual(response.status_code, 403)

    def test_contact_photo_returns_image_for_owner(self):
        contact = self._contact_with_photo(self.user)
        self.client.force_login(self.user)
        response = self.client.get(reverse("contacts:photo", args=[contact.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("image/"))
        self.assertGreater(len(b"".join(response.streaming_content)), 0)

    def test_contact_photo_404_when_missing(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        self.client.force_login(self.user)
        response = self.client.get(reverse("contacts:photo", args=[contact.pk]))
        self.assertEqual(response.status_code, 404)

    @override_settings(MEDIA_URL="/media/")
    def test_direct_media_url_not_served(self):
        contact = self._contact_with_photo(self.user)
        self.client.force_login(self.user)
        response = self.client.get(contact.photo.url)
        self.assertEqual(response.status_code, 404)
