""" Test session selection for the contacts app """

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from contacts.session_selection import (
    IMPORT_ERRORS_SESSION_KEY,
    IMPORT_ERRORS_USER_KEY,
    SELECTED_SESSION_KEY,
    SESSION_USER_KEY,
    bind_import_errors_user,
    bind_selection_user,
    clear_import_errors,
    clear_selected_ids,
    get_import_errors,
    set_import_errors,
)


class SessionSelectionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("ada", password="pass")
        self.other = User.objects.create_user("bob", password="pass")

    def _request(self):
        request = self.factory.get("/")
        request.session = self.client.session
        return request

    def test_clear_selected_ids_no_op_without_session(self):
        request = self.factory.get("/")
        clear_selected_ids(request)

    def test_clear_import_errors_no_op_without_session(self):
        request = self.factory.get("/")
        clear_import_errors(request)

    def test_bind_selection_user_no_op_without_session(self):
        bind_selection_user(self.factory.get("/"), self.user)

    def test_bind_import_errors_user_no_op_without_session(self):
        bind_import_errors_user(self.factory.get("/"), self.user)

    def test_bind_selection_user_clears_on_user_change(self):
        request = self._request()
        request.session[SELECTED_SESSION_KEY] = ["1"]
        request.session[SESSION_USER_KEY] = str(self.user.pk)
        request.session.save()

        bind_selection_user(request, self.other)

        self.assertNotIn(SELECTED_SESSION_KEY, request.session)
        self.assertEqual(request.session[SESSION_USER_KEY], str(self.other.pk))

    def test_bind_import_errors_user_clears_on_user_change(self):
        request = self._request()
        request.session[IMPORT_ERRORS_SESSION_KEY] = [{"row_number": 2}]
        request.session[IMPORT_ERRORS_USER_KEY] = str(self.user.pk)
        request.session.save()

        bind_import_errors_user(request, self.other)

        self.assertNotIn(IMPORT_ERRORS_SESSION_KEY, request.session)
        self.assertEqual(request.session[IMPORT_ERRORS_USER_KEY], str(self.other.pk))

    def test_set_import_errors_without_authenticated_user(self):
        request = self._request()
        request.user = AnonymousUser()

        set_import_errors(request, [{"row_number": 2}])

        self.assertIn(IMPORT_ERRORS_SESSION_KEY, request.session)
        self.assertNotIn(IMPORT_ERRORS_USER_KEY, request.session)

    def test_set_import_errors_with_authenticated_user(self):
        request = self._request()
        request.user = self.user

        set_import_errors(request, [{"row_number": 2}])

        self.assertEqual(request.session[IMPORT_ERRORS_USER_KEY], str(self.user.pk))

    def test_get_import_errors_requires_authentication(self):
        request = self._request()
        request.user = AnonymousUser()
        request.session[IMPORT_ERRORS_SESSION_KEY] = [{"row_number": 2}]
        request.session[IMPORT_ERRORS_USER_KEY] = str(self.user.pk)
        request.session.save()

        self.assertIsNone(get_import_errors(request))

    def test_get_import_errors_requires_matching_user(self):
        request = self._request()
        request.user = self.user
        request.session[IMPORT_ERRORS_SESSION_KEY] = [{"row_number": 2}]
        request.session[IMPORT_ERRORS_USER_KEY] = str(self.other.pk)
        request.session.save()

        self.assertIsNone(get_import_errors(request))

    def test_get_import_errors_returns_payload_for_owner(self):
        request = self._request()
        request.user = self.user
        errors = [{"row_number": 2, "data": {}, "errors": {}}]
        request.session[IMPORT_ERRORS_SESSION_KEY] = errors
        request.session[IMPORT_ERRORS_USER_KEY] = str(self.user.pk)
        request.session.save()

        self.assertEqual(get_import_errors(request), errors)

    def test_set_import_errors_no_op_without_session(self):
        set_import_errors(self.factory.get("/"), [])

    def test_get_import_errors_no_op_without_session(self):
        request = self.factory.get("/")
        request.user = self.user
        self.assertIsNone(get_import_errors(request))
