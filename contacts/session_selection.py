SELECTED_SESSION_KEY = "selected_contact_ids"
SESSION_USER_KEY = "selected_contact_user_id"
IMPORT_ERRORS_SESSION_KEY = "last_import_errors"
IMPORT_ERRORS_USER_KEY = "last_import_errors_user_id"


def clear_selected_ids(request):
    if request and hasattr(request, "session"):
        request.session.pop(SELECTED_SESSION_KEY, None)
        request.session.modified = True


def clear_import_errors(request):
    if request and hasattr(request, "session"):
        request.session.pop(IMPORT_ERRORS_SESSION_KEY, None)
        request.session.pop(IMPORT_ERRORS_USER_KEY, None)
        request.session.modified = True


def bind_selection_user(request, user):
    if not request or not hasattr(request, "session"):
        return
    user_id = str(user.pk)
    bound = request.session.get(SESSION_USER_KEY)
    if bound is not None and bound != user_id:
        clear_selected_ids(request)
    request.session[SESSION_USER_KEY] = user_id
    request.session.modified = True


def bind_import_errors_user(request, user):
    if not request or not hasattr(request, "session"):
        return
    user_id = str(user.pk)
    bound = request.session.get(IMPORT_ERRORS_USER_KEY)
    if bound is not None and bound != user_id:
        clear_import_errors(request)
    request.session[IMPORT_ERRORS_USER_KEY] = user_id
    request.session.modified = True


def set_import_errors(request, errors):
    if not request or not hasattr(request, "session"):
        return
    request.session[IMPORT_ERRORS_SESSION_KEY] = errors
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        request.session[IMPORT_ERRORS_USER_KEY] = str(user.pk)
    request.session.modified = True


def get_import_errors(request):
    if not request or not hasattr(request, "session"):
        return None
    raw = request.session.get(IMPORT_ERRORS_SESSION_KEY)
    if not raw:
        return None
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    bound = request.session.get(IMPORT_ERRORS_USER_KEY)
    if bound != str(user.pk):
        return None
    return raw
