""" Test media import fixes for the contacts app """

from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from contacts.exporters import UTF8_BOM, csv_contact_rows
from contacts.forms import ContactForm
from contacts.importers import MAX_IMPORT_ERRORS, stream_import_contacts
from contacts.models import Contact, Email, Phone


class MediaImportExportFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def _jpeg_upload(self, size=(40, 40)):
        buffer = BytesIO()
        Image.new("RGB", size, color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("photo.jpg", buffer.read(), content_type="image/jpeg")

    def test_contact_form_rejects_invalid_photo_content_type(self):
        upload = SimpleUploadedFile("photo.txt", b"not-an-image", content_type="text/plain")
        form = ContactForm(
            data={"first_name": "Ada", "phone": "", "email": ""},
            files={"photo": upload},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)

    def test_contact_form_rejects_oversized_dimensions(self):
        upload = self._jpeg_upload(size=(9000, 9000))
        form = ContactForm(
            data={"first_name": "Ada", "phone": "", "email": ""},
            files={"photo": upload},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)

    @override_settings(MEDIA_ROOT="test-media/")
    def test_replaced_contact_photo_deletes_previous_file(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        first = self._jpeg_upload()
        contact.photo.save("first.jpg", first, save=True)
        first_name = contact.photo.name
        second = self._jpeg_upload()
        contact.photo.save("second.jpg", second, save=True)
        self.assertFalse(default_storage.exists(first_name))
        self.assertTrue(default_storage.exists(contact.photo.name))

    @override_settings(MEDIA_ROOT="test-media/")
    def test_deleted_contact_removes_photo_file(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact.photo.save("delete-me.jpg", self._jpeg_upload(), save=True)
        stored_name = contact.photo.name
        contact.delete()
        self.assertFalse(default_storage.exists(stored_name))

    def test_csv_export_includes_utf8_bom(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        rows = list(csv_contact_rows(Contact.objects.for_user(self.user)))
        self.assertTrue(rows[0].startswith(UTF8_BOM))

    def test_import_skips_duplicate_phone(self):
        Contact.objects.create(owner=self.user, first_name="Existing", phone="+14155552671")
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            b"First Name,Last Name,Phone\nBob,Smith,(415) 555-2671\n",
            content_type="text/csv",
        )
        result = stream_import_contacts(self.user, uploaded)
        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertFalse(Contact.objects.filter(first_name="Bob").exists())

    def test_import_caps_session_errors_constant(self):
        self.assertEqual(MAX_IMPORT_ERRORS, 500)

    def test_vcard_uid_uses_contact_uuid(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        response = self.client.get(reverse("contacts:vcard_one", args=[contact.pk]))
        self.assertIn(f"UID:{contact.uuid}@address-book-portal".encode(), response.content)

    def test_csv_error_report_downloadable_twice(self):
        session = self.client.session
        session["last_import_errors"] = [
            {"row_number": 2, "data": {}, "errors": {"first_name": ["Required."]}}
        ]
        session["last_import_errors_user_id"] = str(self.user.pk)
        session.save()
        first = self.client.get(reverse("contacts:csv_error_report"))
        second = self.client.get(reverse("contacts:csv_error_report"))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
