from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from contacts import views
from contacts.models import Contact


class ViewHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("ada", password="pass")

    def test_is_htmx_detects_header(self):
        request = self.factory.get("/", HTTP_HX_REQUEST="true")
        self.assertTrue(views.is_htmx(request))
        self.assertFalse(views.is_htmx(self.factory.get("/")))

    def test_request_list_mode_prefers_post(self):
        request = self.factory.post("/", {"list_mode": "archive"}, QUERY_STRING="list_mode=active")
        self.assertEqual(views.request_list_mode(request), "archive")

    def test_request_list_mode_falls_back_to_default(self):
        request = self.factory.get("/")
        self.assertEqual(views.request_list_mode(request, default="favorites"), "favorites")

    def test_selected_ids_round_trip(self):
        request = self.factory.get("/")
        request.session = self.client.session
        views.set_selected_ids(request, ["3", "1", 3])
        self.assertEqual(views.selected_ids(request), {"1", "3"})

    def test_prune_selected_ids_drops_missing_contacts(self):
        contact = Contact.objects.create(owner=self.user, first_name="Ada")
        request = self.factory.get("/")
        request.session = self.client.session
        request.user = self.user
        views.set_selected_ids(request, [str(contact.pk), "9999"])
        pruned = views.prune_selected_ids(request)
        self.assertEqual(pruned, {str(contact.pk)})

    def test_prune_selected_ids_no_op_when_empty(self):
        request = self.factory.get("/")
        request.session = self.client.session
        request.user = self.user
        self.assertEqual(views.prune_selected_ids(request), set())

    def test_htmx_redirect_sets_header(self):
        response = views.htmx_redirect("/contacts/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], "/contacts/")

    def test_selected_contacts_for_mode_archive(self):
        active = Contact.objects.create(owner=self.user, first_name="Active")
        archived = Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        selected = {str(active.pk), str(archived.pk)}
        qs = views.selected_contacts_for_mode(self.user, selected, "archive")
        self.assertEqual(list(qs), [archived])

    def test_selected_contacts_for_mode_favorites(self):
        favorite = Contact.objects.create(owner=self.user, first_name="Star", is_favorite=True)
        Contact.objects.create(owner=self.user, first_name="Plain")
        selected = {str(favorite.pk), "999"}
        qs = views.selected_contacts_for_mode(self.user, selected, "favorites")
        self.assertEqual(list(qs), [favorite])

    def test_selected_contacts_for_mode_active(self):
        active = Contact.objects.create(owner=self.user, first_name="Active")
        archived = Contact.objects.create(owner=self.user, first_name="Archived", is_archived=True)
        selected = {str(active.pk), str(archived.pk)}
        qs = views.selected_contacts_for_mode(self.user, selected, "active")
        self.assertEqual(list(qs), [active])

    def test_htmx_list_or_redirect_returns_rows_when_mode_not_in_refresh(self):
        request = self.factory.get("/", HTTP_HX_REQUEST="true", QUERY_STRING="list_mode=active")
        request.user = self.user
        request.session = self.client.session
        response = views.htmx_list_or_redirect(
            request,
            redirect_to="/contacts/1/",
            refresh_modes={"archive"},
        )
        self.assertEqual(response.status_code, 200)

    def test_htmx_list_or_redirect_returns_none_for_full_page(self):
        request = self.factory.get("/")
        request.user = self.user
        self.assertIsNone(
            views.htmx_list_or_redirect(request, redirect_to="/contacts/", refresh_modes=set())
        )

    def test_base_contact_queryset_tag_filter(self):
        from contacts.models import Tag

        tag = Tag.objects.create(owner=self.user, name="VIP", color="#2563eb")
        tagged = Contact.objects.create(owner=self.user, first_name="Tagged")
        Contact.objects.create(owner=self.user, first_name="Plain")
        tag.contacts.add(tagged)
        request = self.factory.get("/", {"tag": str(tag.pk)})
        request.user = self.user
        qs = views.base_contact_queryset(request)
        self.assertEqual(list(qs), [tagged])

    def test_base_contact_queryset_desc_sort(self):
        Contact.objects.create(owner=self.user, first_name="Zed", last_name="Zulu")
        Contact.objects.create(owner=self.user, first_name="Amy", last_name="Alpha")
        request = self.factory.get("/", {"sort": "name", "dir": "desc"})
        request.user = self.user
        names = [c.first_name for c in views.base_contact_queryset(request)]
        self.assertEqual(names, ["Zed", "Amy"])

    def test_contact_form_context(self):
        context = views.contact_form_context(form=None, contact=None, list_mode="archive")
        self.assertEqual(context["list_mode"], "archive")
