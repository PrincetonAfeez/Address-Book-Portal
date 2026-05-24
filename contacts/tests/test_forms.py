""" Test forms for the contacts app """

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from contacts.forms import ContactForm
from contacts.models import Contact, Phone


class ContactFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def _make_image(self):
        buffer = BytesIO()
        Image.new("RGB", (100, 100), color="red").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("photo.jpg", buffer.read(), content_type="image/jpeg")

    def test_contact_form_clears_photo(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            phone="+14155552671",
        )
        contact.photo = self._make_image()
        contact.save(resize_photo=True)

        form = ContactForm(
            data={
                "first_name": "Ada",
                "last_name": "",
                "email": "",
                "phone": "+14155552671",
                "company": "",
                "job_title": "",
                "birthday": "",
                "notes": "",
                "photo-clear": "on",
            },
            instance=contact,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertFalse(saved.photo)

    def test_sync_primary_records_creates_phone_row(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            phone="+14155552671",
        )
        form = ContactForm(instance=contact)
        form.sync_primary_records(contact)

        phone = contact.phones.get()
        self.assertEqual(phone.number, "+14155552671")
        self.assertEqual(phone.label, Phone.MOBILE)
        self.assertTrue(phone.is_scalar_sync)

    def test_first_name_is_required(self):
        form = ContactForm(data={"first_name": "", "phone": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)

    def test_contact_form_edit_without_photo_change_skips_resize(self):
        contact = Contact.objects.create(
            owner=self.user,
            first_name="Ada",
            phone="+14155552671",
        )
        contact.photo = self._make_image()
        contact.save(resize_photo=True)
        form = ContactForm(
            data={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "",
                "phone": "+14155552671",
                "company": "",
                "job_title": "",
                "birthday": "",
                "notes": "",
            },
            instance=contact,
        )
        self.assertTrue(form.is_valid(), form.errors)
        with patch.object(Contact, "_resize_photo") as mock_resize:
            form.save()
            mock_resize.assert_not_called()
