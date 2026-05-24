""" Test final coverage for the contacts app """

import importlib
from pathlib import Path
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase

from contacts.admin import ContactAdmin, GroupAdmin, OwnerScopedAdmin, RelatedContactAdmin, TagAdmin
from contacts.exporters import _utf8_chunk, _vcard_photo_line, fold_line
from contacts.forms import TagForm
from contacts.importers import build_field_map, decoded_csv_lines
from contacts.models import Contact, Group, Phone, Tag


class AdminRemainingCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("bob", password="pass")
        self.site = AdminSite()
        self.factory = RequestFactory()

    def test_owner_scoped_admin_assigns_owner_on_create(self):
        self.user.is_staff = True
        self.user.save()
        request = self.factory.post("/admin/")
        request.user = self.user
        group = Group(name="Friends")
        admin = GroupAdmin(Group, self.site)
        admin.save_model(request, group, form=None, change=False)
        self.assertEqual(group.owner, self.user)

    def test_group_admin_superuser_sees_owner_filter_and_field(self):
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = GroupAdmin(Group, self.site)
        self.assertEqual(admin.get_list_filter(request), admin.list_filter)
        self.assertIn("owner", admin.get_fields(request))

    def test_tag_admin_superuser_sees_owner_filter_and_field(self):
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = TagAdmin(Tag, self.site)
        self.assertEqual(admin.get_list_filter(request), admin.list_filter)
        self.assertIn("owner", admin.get_fields(request))

    def test_related_contact_admin_superuser_sees_all_phones(self):
        own = Contact.objects.create(owner=self.user, first_name="Ada")
        other = Contact.objects.create(owner=self.other, first_name="Bob")
        Phone.objects.create(contact=own, number="+14155552671")
        Phone.objects.create(contact=other, number="+14155552672")
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = RelatedContactAdmin(Phone, self.site)
        self.assertEqual(admin.get_queryset(request).count(), 2)

    def test_owner_scoped_admin_superuser_queryset_unfiltered(self):
        Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.other, first_name="Bob")
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = OwnerScopedAdmin(Contact, self.site)
        self.assertEqual(admin.get_queryset(request).count(), 2)

    def test_contact_admin_superuser_get_fieldsets_unmodified(self):
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = ContactAdmin(Contact, self.site)
        fieldsets = admin.get_fieldsets(request)
        self.assertIn("owner", fieldsets[0][1]["fields"])


class ExporterRemainingCoverageTests(SimpleTestCase):
    def test_utf8_chunk_trims_invalid_trailing_byte(self):
        encoded = "é".encode("utf-8")
        self.assertEqual(_utf8_chunk(encoded[:1]), b"")

    def test_fold_line_stops_on_unbreakable_invalid_utf8(self):
        folded = fold_line("\xff" * 80)
        self.assertIsInstance(folded, str)

    def test_fold_line_breaks_when_chunk_is_empty(self):
        with patch("contacts.exporters._utf8_chunk", return_value=b""):
            folded = fold_line("x" * 100)
        self.assertEqual(folded, "")


class ExporterJpgPhotoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_vcard_photo_normalizes_jpg_type_to_jpeg(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact.photo.save(
            "ada.jpg",
            SimpleUploadedFile("ada.jpg", b"fake-jpg", content_type="image/jpg"),
            save=True,
        )
        with patch("contacts.exporters.mimetypes.guess_type", return_value=("image/jpg", None)):
            line = _vcard_photo_line(contact)
        self.assertIn("TYPE=JPEG:", line)


class ImporterRemainingCoverageTests(SimpleTestCase):
    def test_build_field_map_skips_blank_headers(self):
        field_map = build_field_map(["First Name", "", "Last Name"])
        self.assertEqual(field_map, {"First Name": "first_name", "Last Name": "last_name"})

    def test_decoded_csv_lines_yields_cr_only_separators(self):
        class ChunkFile:
            def chunks(self):
                yield b"First\rSecond"

        lines = list(decoded_csv_lines(ChunkFile()))
        self.assertEqual(lines, ["First\r", "Second"])

    def test_error_report_rows_coerces_string_messages(self):
        from contacts.importers import error_report_rows

        class RawError:
            row_number = 4
            errors = {"file": "bad header"}

        rows = list(error_report_rows([RawError()]))
        self.assertIn("bad header", rows[1])


class ModelRemainingCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_photo_url_empty_when_no_photo(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        self.assertEqual(contact.photo_url, "")

    def test_resize_photo_noops_without_photo(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact._resize_photo()


class TagFormCleanCoverageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_tag_form_clean_adds_color_error_from_validator(self):
        form = TagForm(user=self.user)
        form.cleaned_data = {"name": "VIP", "color": "not-hex"}
        form.clean()
        self.assertIn("color", form.errors)


class BaseSettingsLoggingTests(SimpleTestCase):
    def test_logging_uses_console_only_when_log_dir_unwritable(self):
        import config.settings.base as base

        with patch.object(Path, "mkdir", side_effect=OSError):
            reloaded = importlib.reload(base)
            self.assertEqual(reloaded.LOG_HANDLERS, ["console"])
            self.assertNotIn("file", reloaded.LOGGING_HANDLERS)
        importlib.reload(base)
