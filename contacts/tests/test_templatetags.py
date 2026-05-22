from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import RequestFactory, TestCase


class QuerystringTagTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("ada", password="pass")

    def _render_indicator(self, params, sort="name", direction="asc"):
        request = self.factory.get("/contacts/", params)
        request.user = self.user
        return Template("{% load querystring %}{% sort_indicator 'name' %}").render(
            Context({"request": request, "sort": sort, "direction": direction})
        )

    def test_sort_indicator_shows_asc_arrow_for_active_column(self):
        rendered = self._render_indicator({"sort": "name", "dir": "asc"}, sort="name", direction="asc")
        self.assertEqual(rendered.strip(), "▲")

    def test_sort_indicator_shows_desc_arrow(self):
        rendered = self._render_indicator({"sort": "name", "dir": "desc"}, sort="name", direction="desc")
        self.assertEqual(rendered.strip(), "▼")

    def test_sort_indicator_empty_for_other_column(self):
        rendered = self._render_indicator({"sort": "company", "dir": "asc"}, sort="company", direction="asc")
        self.assertEqual(rendered.strip(), "")

    def test_sort_link_toggles_direction(self):
        request = self.factory.get("/contacts/", {"sort": "name", "dir": "asc"})
        request.user = self.user
        rendered = Template('{% load querystring %}{% sort_link "name" "asc" %}').render(
            Context({"request": request, "sort": "name", "direction": "asc"})
        )

        self.assertIn("dir=desc", rendered)

    def test_qs_replace_adds_and_removes_params(self):
        request = self.factory.get("/contacts/", {"q": "ada", "page": "2"})
        request.user = self.user
        rendered = Template(
            '{% load querystring %}{% qs_replace q="new" page="" %}'
        ).render(Context({"request": request}))
        self.assertIn("q=new", rendered)
        self.assertNotIn("page=", rendered)
