""" Test coverage max for the contacts app """

from io import BytesIO
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from contacts.admin import ContactAdmin, GroupAdmin, RelatedContactAdmin, TagAdmin
from contacts.exporters import _utf8_chunk, _vcard_photo_line, contact_to_vcard, format_vcard_phone
from contacts.forms import BulkActionForm, ContactForm, GroupForm, SignupForm, TagForm
from contacts.importers import RowError, normalize_field_errors, parse_date, stream_import_contacts
from contacts.models import Contact, Email, Group, Phone, Tag, contact_photo_path
from contacts.utils import next_birthday_on_or_after


class ImporterExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_normalize_field_errors_coerces_scalar(self):
        self.assertEqual(
            normalize_field_errors({"row": "bad"}),
            {"row": ["bad"]},
        )

    def test_normalize_field_errors_coerces_other_types(self):
        self.assertEqual(
            normalize_field_errors({"row": 404}),
            {"row": ["404"]},
        )

    def test_row_error_post_init_normalizes_strings(self):
        error = RowError(2, {}, {"row": "Too many columns."})
        self.assertEqual(error.errors["row"], ["Too many columns."])

    def test_parse_date_invalid_format(self):
        with self.assertRaises(ValidationError):
            parse_date("not-a-date")

    def test_stream_import_duplicate_headers(self):
        uploaded = SimpleUploadedFile(
            "contacts.csv",
            b"First Name,first name\nAda,Lovelace\n",
            content_type="text/csv",
        )
        result = stream_import_contacts(self.user, uploaded)
        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.failed_count, 1)

    def test_decoded_csv_lines_handles_mixed_newlines(self):
        from contacts.importers import decoded_csv_lines

        uploaded = SimpleUploadedFile(
            "contacts.csv",
            "First Name,Last Name\rAda,Lovelace\nBob,Bryant\r\n".encode(),
            content_type="text/csv",
        )
        payload = "".join(decoded_csv_lines(uploaded))
        self.assertIn("Ada,Lovelace", payload)
        self.assertIn("Bob,Bryant", payload)


class ExporterExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_format_vcard_phone_unknown_label(self):
        line = format_vcard_phone("+14155552671", "satellite")
        self.assertIn("TYPE=SATELLITE:", line)

    def test_vcard_photo_line_returns_none_when_file_unreadable(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact.photo.name = "missing/photo.jpg"
        self.assertIsNone(_vcard_photo_line(contact))

    def test_utf8_chunk_empty_input(self):
        self.assertEqual(_utf8_chunk(b""), b"")

    def test_vcard_photo_png_type(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact.photo.save(
            "ada.png",
            SimpleUploadedFile("ada.png", b"png-bytes", content_type="image/png"),
            save=True,
        )
        payload = contact_to_vcard(contact)
        self.assertIn("PHOTO;ENCODING=b;TYPE=PNG:", payload)


class FormGapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_group_form_rejects_blank_name(self):
        form = GroupForm(user=self.user)
        form.cleaned_data = {"name": "   "}
        with self.assertRaises(ValidationError):
            form.clean_name()

    def test_tag_form_rejects_blank_name(self):
        form = TagForm(user=self.user)
        form.cleaned_data = {"name": "  ", "color": "#2563eb"}
        with self.assertRaises(ValidationError):
            form.clean_name()

    def test_tag_form_edit_excludes_self_from_duplicate_check(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        form = TagForm({"name": "vip", "color": "#2563eb"}, instance=tag, user=self.user)
        self.assertTrue(form.is_valid())

    def test_group_form_edit_excludes_self_from_duplicate_check(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        form = GroupForm({"name": "friends"}, instance=group, user=self.user)
        self.assertTrue(form.is_valid())

    def test_signup_form_save_without_commit(self):
        form = SignupForm(
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save(commit=False)
        self.assertEqual(user.email, "new@example.com")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_contact_form_save_without_commit(self):
        form = ContactForm({"first_name": "Ada", "phone": ""})
        self.assertTrue(form.is_valid())
        contact = form.save(commit=False)
        self.assertEqual(contact.first_name, "Ada")
        self.assertFalse(Contact.objects.filter(first_name="Ada").exists())

    def test_bulk_action_form_archive_mode_choices(self):
        form = BulkActionForm(user=self.user, list_mode="archive")
        actions = [choice[0] for choice in form.fields["action"].choices]
        self.assertIn("delete", actions)
        self.assertIn("restore", actions)
        self.assertNotIn("archive", actions)


class ModelGapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")

    def test_display_phone_from_related_row(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        Phone.objects.create(contact=contact, number="+14155552671", label=Phone.MOBILE)
        self.assertEqual(contact.display_phone, "+14155552671")

    def test_display_email_scalar_preferred_over_related(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada", email="primary@example.com")
        Email.objects.create(contact=contact, address="other@example.com", label=Email.OTHER)
        self.assertEqual(contact.display_email, "primary@example.com")

    def test_contact_photo_path_includes_owner(self):
        contact = Contact(owner=self.user, first_name="Ada")
        path = contact_photo_path(contact, "photo.JPG")
        self.assertIn(f"user_{self.user.pk}", path)
        self.assertTrue(path.endswith(".jpg"))

    def test_photo_resize_logs_and_continues_on_failure(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        contact.photo.save(
            "bad.jpg",
            SimpleUploadedFile("bad.jpg", b"not-an-image", content_type="image/jpeg"),
            save=True,
        )
        with patch("contacts.models.logger.warning") as warning:
            contact.save(resize_photo=True)
        warning.assert_called_once()

    def test_owned_manager_for_anonymous_user_returns_none(self):
        from django.contrib.auth.models import AnonymousUser

        Contact.objects.create(owner=self.user, first_name="Ada")
        self.assertEqual(Contact.objects.for_user(AnonymousUser()).count(), 0)


class AdminExtendedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("bob", password="pass")
        self.site = AdminSite()
        self.factory = RequestFactory()

    def test_contact_admin_sync_warning_display(self):
        admin = ContactAdmin(Contact, self.site)
        self.assertIn("Portal edits sync", admin.sync_warning(None))

    def test_contact_admin_save_related_syncs_primary_records(self):
        from unittest.mock import Mock

        contact = Contact.objects.create(owner=self.user, first_name="Ada", phone="+14155552671")
        request = self.factory.post("/admin/")
        request.user = self.user
        admin = ContactAdmin(Contact, self.site)
        form = Mock(instance=contact)
        admin.save_related(request, form, formsets=[], change=True)
        self.assertEqual(contact.phones.count(), 1)

    def test_group_admin_m2m_queryset_scoped_for_staff(self):
        own = Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.other, first_name="Bob")
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/")
        request.user = self.user
        admin = GroupAdmin(Group, self.site)
        field = admin.formfield_for_manytomany(Group.contacts.field, request)
        self.assertEqual(list(field.queryset), [own])

    def test_tag_admin_hides_owner_for_staff(self):
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/")
        request.user = self.user
        admin = TagAdmin(Tag, self.site)
        self.assertNotIn("owner", admin.get_fields(request))

    def test_related_contact_admin_scopes_phones(self):
        own = Contact.objects.create(owner=self.user, first_name="Ada")
        other = Contact.objects.create(owner=self.other, first_name="Bob")
        own_phone = Phone.objects.create(contact=own, number="+14155552671")
        Phone.objects.create(contact=other, number="+14155552672")
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/")
        request.user = self.user
        admin = RelatedContactAdmin(Phone, self.site)
        self.assertEqual(list(admin.get_queryset(request)), [own_phone])

    def test_related_contact_admin_scopes_contact_fk_for_staff(self):
        own = Contact.objects.create(owner=self.user, first_name="Ada")
        Contact.objects.create(owner=self.other, first_name="Bob")
        self.user.is_staff = True
        self.user.save()
        request = self.factory.get("/admin/")
        request.user = self.user
        admin = RelatedContactAdmin(Phone, self.site)
        field = admin.formfield_for_foreignkey(Phone.contact.field, request)
        self.assertEqual(list(field.queryset), [own])

    def test_superuser_contact_admin_includes_owner_field(self):
        request = self.factory.get("/admin/")
        request.user = User.objects.create_superuser("root", password="pass")
        admin = ContactAdmin(Contact, self.site)
        fields = admin.get_fieldsets(request)[0][1]["fields"]
        self.assertIn("owner", fields)


class ViewGapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ada", password="pass")
        self.client.force_login(self.user)

    def test_signup_redirects_when_logged_in(self):
        response = self.client.get(reverse("signup"))
        self.assertRedirects(response, reverse("contacts:dashboard"))

    def test_organization_create_tag_success(self):
        response = self.client.post(
            reverse("contacts:organization"),
            {"kind": "tag", "tag-name": "VIP", "tag-color": "#2563eb"},
        )
        self.assertRedirects(response, reverse("contacts:organization"))
        self.assertTrue(Tag.objects.filter(name="VIP").exists())

    def test_organization_tag_integrity_error_handled(self):
        Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        with patch.object(Tag, "save", side_effect=IntegrityError):
            response = self.client.post(
                reverse("contacts:organization"),
                {"kind": "tag", "tag-name": "New", "tag-color": "#10b981"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a tag")

    def test_organization_group_integrity_error_handled(self):
        Group.objects.create(owner=self.user, name="Friends")
        with patch.object(Group, "save", side_effect=IntegrityError):
            response = self.client.post(
                reverse("contacts:organization"),
                {"kind": "group", "group-name": "NewGroup"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a group")

    def test_bulk_add_group_action(self):
        group = Group.objects.create(owner=self.user, name="Friends")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_group", "group": str(group.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(contact, group.contacts.all())

    def test_bulk_add_tag_action(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_tag", "tag": str(tag.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(contact, tag.contacts.all())

    def test_bulk_remove_tag_action(self):
        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        tag.contacts.add(contact)
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "remove_tag", "tag": str(tag.pk), "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(contact, tag.contacts.all())

    def test_bulk_action_invalid_form(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        session = self.client.session
        session["selected_contact_ids"] = [str(contact.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:bulk_action"),
            {"action": "add_group", "list_mode": "active"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check the bulk action fields.")
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_selection_page_deselect_owned_ids_only(self):
        c1 = Contact.objects.create(owner=self.user, first_name="One")
        c2 = Contact.objects.create(owner=self.user, first_name="Two")
        session = self.client.session
        session["selected_contact_ids"] = [str(c1.pk), str(c2.pk)]
        session.save()
        response = self.client.post(
            reverse("contacts:selection_page"),
            {
                "contact_ids": [str(c1.pk), "9999"],
                "selected": "false",
                "list_mode": "active",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(self.client.session["selected_contact_ids"]), {str(c2.pk)})

    def test_csv_import_get_renders_form(self):
        response = self.client.get(reverse("contacts:csv_import"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Primary fields only")

    def test_csv_export_with_mode_and_filters(self):
        Contact.objects.create(owner=self.user, first_name="Ada", is_favorite=True)
        response = self.client.get(reverse("contacts:csv_export"), {"mode": "favorites"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ada", b"".join(response.streaming_content))


class UtilsGapTests(SimpleTestCase):
    def test_next_birthday_on_or_after_returns_none_when_no_future_candidate(self):
        from datetime import date
        from unittest.mock import patch

        birthday = date(2000, 1, 1)
        with patch("contacts.utils.birthday_in_year", return_value=date(2020, 1, 1)):
            self.assertIsNone(next_birthday_on_or_after(birthday, date(2025, 6, 1)))


class ValidatorGapTests(SimpleTestCase):
    def test_rejects_non_digit_compact_phone(self):
        from contacts.validators import normalize_phone_number

        with self.assertRaises(ValidationError):
            normalize_phone_number("12-34-++")
