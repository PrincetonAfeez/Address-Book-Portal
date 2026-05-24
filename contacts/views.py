""" Views for the contacts app """

from datetime import timedelta
import mimetypes

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods, require_POST

from .exporters import contact_to_vcard, csv_contact_rows, vcards_for_contacts
from .forms import BulkActionForm, CSVImportForm, ContactForm, GroupForm, SignupForm, TagForm
from .importers import MAX_IMPORT_ERRORS, error_report_rows, stream_import_contacts
from .models import Contact, Group, Tag
from .utils import upcoming_birthdays


from .session_selection import (
    clear_import_errors,
    clear_selected_ids,
    get_import_errors,
    get_selected_ids,
    set_import_errors,
)
SORTS = {
    "name": ("last_name", "first_name"),
    "company": ("company", "last_name", "first_name"),
    "created": ("created_at",),
    "updated": ("updated_at",),
}
LIST_MODES = frozenset({"active", "archive", "favorites"})


def format_count_message(count, singular, plural):
    return ngettext(singular, plural, count) % {"count": count}


def signup(request):
    if request.user.is_authenticated:
        return redirect("contacts:dashboard")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome in. Your address book is ready.")
            return redirect("contacts:dashboard")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def normalize_list_mode(value, default="active"):
    if value in LIST_MODES:
        return value
    return default


def request_list_mode(request, default=""):
    raw = request.POST.get("list_mode") or request.GET.get("list_mode") or default
    if not raw:
        return default
    return normalize_list_mode(raw, default or "active")


def selected_ids(request):
    return get_selected_ids(request)


def set_selected_ids(request, ids):
    from .session_selection import SELECTED_SESSION_KEY, SESSION_USER_KEY

    request.session[SELECTED_SESSION_KEY] = sorted({str(contact_id) for contact_id in ids})
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        request.session[SESSION_USER_KEY] = str(user.pk)
    request.session.modified = True


def prune_selected_ids(request):
    current = selected_ids(request)
    if not current:
        return current
    valid = {
        str(pk)
        for pk in Contact.objects.for_user(request.user)
        .filter(pk__in=current)
        .values_list("pk", flat=True)
    }
    if valid != current:
        set_selected_ids(request, valid)
    return valid


def prune_selected_ids_for_mode(request, mode):
    current = prune_selected_ids(request)
    mode_valid = {
        str(pk)
        for pk in selected_contacts_for_mode(request.user, current, mode).values_list("pk", flat=True)
    }
    if mode_valid != current:
        set_selected_ids(request, mode_valid)
    return mode_valid


def remove_contact_from_selection(request, contact_id):
    current = selected_ids(request)
    current.discard(str(contact_id))
    set_selected_ids(request, current)


def htmx_redirect(url):
    response = HttpResponse(status=204)
    response["HX-Redirect"] = url
    return response


def selected_contacts_for_mode(user, selected, list_mode):
    qs = Contact.objects.for_user(user).filter(pk__in=selected)
    if list_mode == "archive":
        return qs.archived()
    if list_mode == "favorites":
        return qs.favorites()
    return qs.active()


def htmx_list_or_redirect(request, *, redirect_to, refresh_modes=None):
    if not is_htmx(request):
        return None
    list_mode = request_list_mode(request)
    if list_mode and list_mode not in (refresh_modes or set()):
        return rows_response(request, mode=list_mode, clear_modal=True)
    return htmx_redirect(redirect_to)


def base_contact_queryset(request, mode="active"):
    mode = normalize_list_mode(mode)
    qs = (
        Contact.objects.for_user(request.user)
        .prefetch_related("groups", "tags", "phones", "emails")
        .distinct()
    )
    if mode == "archive":
        qs = qs.archived()
    elif mode == "favorites":
        qs = qs.favorites()
    else:
        qs = qs.active()

    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group")
    tag_id = request.GET.get("tag")

    qs = qs.search(query)
    if group_id:
        if Group.objects.for_user(request.user).filter(pk=group_id).exists():
            qs = qs.filter(groups__id=group_id)
        else:
            return qs.none()
    if tag_id:
        if Tag.objects.for_user(request.user).filter(pk=tag_id).exists():
            qs = qs.filter(tags__id=tag_id)
        else:
            return qs.none()

    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    fields = SORTS.get(sort, SORTS["name"])
    if direction == "desc":
        fields = tuple(f"-{field}" for field in fields)
    return qs.order_by(*fields).distinct()


def list_context(request, mode="active"):
    qs = base_contact_queryset(request, mode)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    selected = prune_selected_ids_for_mode(request, mode)
    mode_selected_ids = set(selected)
    page_contact_ids = {str(contact.id) for contact in page_obj.object_list}
    return {
        "mode": mode,
        "list_mode": mode,
        "contacts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "groups": Group.objects.for_user(request.user).order_by("name"),
        "tags": Tag.objects.for_user(request.user).order_by("name"),
        "selected_ids": mode_selected_ids,
        "selected_count": len(mode_selected_ids),
        "page_all_selected": bool(page_contact_ids and page_contact_ids <= mode_selected_ids),
        "bulk_form": BulkActionForm(user=request.user, list_mode=mode),
        "sort": request.GET.get("sort", "name"),
        "direction": request.GET.get("dir", "asc"),
        "query": request.GET.get("q", ""),
        "is_htmx": is_htmx(request),
    }


def htmx_create_response(request, contact, list_mode):
    if not list_mode:
        return htmx_redirect(contact.get_absolute_url())
    list_mode = normalize_list_mode(list_mode)
    if list_mode == "active":
        return rows_response(request, mode="active", clear_modal=True)
    if list_mode == "favorites" and contact.is_favorite:
        return rows_response(request, mode="favorites", clear_modal=True)
    if list_mode in {"archive", "favorites"}:
        return rows_response(request, mode="active", clear_modal=True)
    return htmx_redirect(contact.get_absolute_url())


def export_queryset(request, mode="active"):
    mode = normalize_list_mode(request.GET.get("mode", mode))
    if request.GET.get("selected") == "1":
        selected = prune_selected_ids(request)
        contacts = selected_contacts_for_mode(request.user, selected, mode)
        filtered_ids = base_contact_queryset(request, mode).values_list("pk", flat=True)
        contacts = contacts.filter(pk__in=filtered_ids)
        sort = request.GET.get("sort", "name")
        direction = request.GET.get("dir", "asc")
        fields = SORTS.get(sort, SORTS["name"])
        if direction == "desc":
            fields = tuple(f"-{field}" for field in fields)
        return contacts.order_by(*fields).distinct()
    return base_contact_queryset(request, mode)


def rows_response(request, mode="active", status=200, *, clear_modal=False):
    context = list_context(request, mode)
    context["clear_modal"] = clear_modal
    return render(
        request,
        "contacts/partials/_contact_rows.html",
        context,
        status=status,
    )


def contact_form_context(form, contact, list_mode=""):
    return {
        "form": form,
        "contact": contact,
        "list_mode": list_mode,
    }


@login_required
def dashboard(request):
    contacts = Contact.objects.for_user(request.user).active()
    today = timezone.localdate()

    context = {
        "total_contacts": contacts.count(),
        "total_groups": Group.objects.for_user(request.user).count(),
        "total_tags": Tag.objects.for_user(request.user).count(),
        "recent_additions": contacts.filter(created_at__date__gte=today - timedelta(days=7))
        .order_by("-created_at")[:5],
        "upcoming_birthdays": upcoming_birthdays(contacts, today=today)[:8],
        "recently_updated": contacts.order_by("-updated_at")[:5],
    }
    return render(request, "contacts/dashboard.html", context)


@login_required
def contact_list(request, mode="active"):
    context = list_context(request, mode)
    if is_htmx(request):
        return render(request, "contacts/partials/_contact_rows.html", context)
    return render(request, "contacts/contact_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def organization(request):
    if request.method == "POST":
        kind = request.POST.get("kind")
        if kind == "group":
            group_form = GroupForm(request.POST, prefix="group", user=request.user)
            tag_form = TagForm(prefix="tag", user=request.user)
            if group_form.is_valid():
                group = group_form.save(commit=False)
                group.owner = request.user
                try:
                    group.save()
                except IntegrityError:
                    group_form.add_error("name", "You already have a group with this name.")
                else:
                    messages.success(request, f"{group.name} group created.")
                    return redirect("contacts:organization")
        elif kind == "tag":
            group_form = GroupForm(prefix="group", user=request.user)
            tag_form = TagForm(request.POST, prefix="tag", user=request.user)
            if tag_form.is_valid():
                tag = tag_form.save(commit=False)
                tag.owner = request.user
                try:
                    tag.save()
                except IntegrityError:
                    tag_form.add_error("name", "You already have a tag with this name.")
                else:
                    messages.success(request, f"{tag.name} tag created.")
                    return redirect("contacts:organization")
        else:
            group_form = GroupForm(prefix="group", user=request.user)
            tag_form = TagForm(prefix="tag", user=request.user)
            messages.error(request, "Choose whether to create a group or a tag.")
    else:
        group_form = GroupForm(prefix="group", user=request.user)
        tag_form = TagForm(prefix="tag", user=request.user)

    return render(
        request,
        "contacts/organization.html",
        {
            "group_form": group_form,
            "tag_form": tag_form,
            "groups": Group.objects.for_user(request.user),
            "tags": Tag.objects.for_user(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def group_edit(request, pk):
    group = Group.objects.get_for_user_or_404(request.user, pk=pk)
    if request.method == "POST":
        form = GroupForm(request.POST, instance=group, user=request.user)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error("name", "You already have a group with this name.")
            else:
                messages.success(request, f"{group.name} group updated.")
                return redirect("contacts:organization")
    else:
        form = GroupForm(instance=group, user=request.user)
    return render(
        request,
        "contacts/organization_edit.html",
        {"form": form, "title": "Edit group", "kind": "group"},
    )


@login_required
@require_http_methods(["GET", "POST"])
def tag_edit(request, pk):
    tag = Tag.objects.get_for_user_or_404(request.user, pk=pk)
    if request.method == "POST":
        form = TagForm(request.POST, instance=tag, user=request.user)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error("name", "You already have a tag with this name.")
            else:
                messages.success(request, f"{tag.name} tag updated.")
                return redirect("contacts:organization")
    else:
        form = TagForm(instance=tag, user=request.user)
    return render(
        request,
        "contacts/organization_edit.html",
        {"form": form, "title": "Edit tag", "kind": "tag"},
    )


@login_required
@require_POST
def group_delete(request, pk):
    group = Group.objects.get_for_user_or_404(request.user, pk=pk)
    group.delete()
    messages.success(request, "Group deleted.")
    return redirect("contacts:organization")


@login_required
@require_POST
def tag_delete(request, pk):
    tag = Tag.objects.get_for_user_or_404(request.user, pk=pk)
    tag.delete()
    messages.success(request, "Tag deleted.")
    return redirect("contacts:organization")


@login_required
def contact_detail(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    return render(request, "contacts/contact_detail.html", {"contact": contact})


@login_required
def contact_photo(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    if not contact.photo:
        raise Http404("Photo not found.")
    content_type, _ = mimetypes.guess_type(contact.photo.name)
    try:
        photo_file = contact.photo.open("rb")
    except FileNotFoundError as exc:
        raise Http404("Photo file is missing.") from exc
    except OSError as exc:
        raise Http404("Photo not found.") from exc
    response = FileResponse(photo_file, content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    return response


def _persist_contact(form, owner):
    contact = form.save(commit=False)
    contact.owner = owner
    contact.save(resize_photo=bool(form.cleaned_data.get("photo")))
    form.sync_primary_records(contact)
    contact.groups.set(form.cleaned_data.get("groups", []))
    contact.tags.set(form.cleaned_data.get("tags", []))
    return contact


@login_required
@require_http_methods(["GET", "POST"])
def contact_create(request):
    list_mode = request_list_mode(request)
    form = ContactForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        contact = _persist_contact(form, request.user)
        messages.success(request, f"{contact.display_name} was added.")
        if is_htmx(request):
            return htmx_create_response(request, contact, list_mode)
        return redirect("contacts:detail", pk=contact.pk)

    template = "contacts/partials/_contact_form.html" if is_htmx(request) else "contacts/contact_form.html"
    response = render(request, template, contact_form_context(form, None, list_mode))
    if request.method == "POST" and is_htmx(request):
        response["HX-Retarget"] = "#modal-root"
        response["HX-Reswap"] = "innerHTML"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def contact_update(request, pk):
    list_mode = request_list_mode(request)
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    form = ContactForm(request.POST or None, request.FILES or None, instance=contact, user=request.user)
    if request.method == "POST" and form.is_valid():
        contact = form.save()
        messages.success(request, f"{contact.display_name} was updated.")
        htmx_response = htmx_list_or_redirect(
            request,
            redirect_to=contact.get_absolute_url(),
        )
        if htmx_response:
            return htmx_response
        return redirect("contacts:detail", pk=contact.pk)

    if is_htmx(request):
        template = "contacts/partials/_contact_form.html"
    else:
        template = "contacts/contact_form.html"
    response = render(request, template, contact_form_context(form, contact, list_mode))
    if request.method == "POST" and is_htmx(request):
        response["HX-Retarget"] = "#modal-root"
        response["HX-Reswap"] = "innerHTML"
    return response


@login_required
@require_POST
def contact_delete(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    contact.soft_delete()
    remove_contact_from_selection(request, contact.pk)
    messages.success(request, f"{contact.display_name} moved to archive.")
    list_mode = request_list_mode(request, default="")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:list"),
    )
    if htmx_response:
        return htmx_response
    if not list_mode:
        if request.POST.get("return_to") == "detail":
            return redirect("contacts:detail", pk=contact.pk)
        return redirect("contacts:list")
    if list_mode == "archive":
        return redirect("contacts:archive")
    if list_mode == "favorites":
        return redirect("contacts:favorites")
    return redirect("contacts:list")


@login_required
@require_POST
def contact_restore(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    contact.restore()
    remove_contact_from_selection(request, contact.pk)
    messages.success(request, f"{contact.display_name} was restored.")
    list_mode = request_list_mode(request, default="")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:archive"),
    )
    if htmx_response:
        return htmx_response
    if not list_mode:
        if request.POST.get("return_to") == "detail":
            return redirect("contacts:detail", pk=contact.pk)
        return redirect("contacts:archive")


@login_required
@require_POST
def contact_permanent_delete(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    if not contact.is_archived:
        messages.error(request, "Only archived contacts can be permanently deleted.")
        return redirect("contacts:detail", pk=contact.pk)
    name = contact.display_name
    contact.delete()
    remove_contact_from_selection(request, pk)
    messages.success(request, f"{name} was permanently deleted.")
    list_mode = request_list_mode(request, default="")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:archive"),
    )
    if htmx_response:
        return htmx_response
    if list_mode == "archive":
        return redirect("contacts:archive")
    return redirect("contacts:list")


@login_required
@require_POST
def contact_toggle_favorite(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    if contact.is_archived:
        messages.error(request, "Restore this contact before changing favorite status.")
        list_mode = request_list_mode(request, default="")
        if is_htmx(request) and list_mode:
            return rows_response(request, mode=list_mode)
        if request.POST.get("return_to") == "detail":
            return redirect("contacts:detail", pk=contact.pk)
        return redirect("contacts:archive")
    contact.is_favorite = not contact.is_favorite
    contact.save(update_fields=["is_favorite", "updated_at"])
    remove_contact_from_selection(request, contact.pk)
    list_mode = request_list_mode(request, default="")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:list"),
    )
    if htmx_response:
        return htmx_response
    if not list_mode:
        if request.POST.get("return_to") == "detail":
            return redirect("contacts:detail", pk=contact.pk)
        return redirect("contacts:list")
    if list_mode == "favorites":
        return redirect("contacts:favorites")
    return redirect("contacts:list")


@login_required
@require_POST
def selection_toggle(request):
    current = selected_ids(request)
    contact_id = request.POST.get("contact_id")
    checked = str(request.POST.get("selected", "")).lower() in {"true", "1", "on"}
    if contact_id and Contact.objects.for_user(request.user).filter(pk=contact_id).exists():
        if checked:
            current.add(str(contact_id))
        else:
            current.discard(str(contact_id))
    set_selected_ids(request, current)
    list_mode = normalize_list_mode(request_list_mode(request, default="active"))
    mode_selected = {
        str(item.pk)
        for item in selected_contacts_for_mode(request.user, current, list_mode)
    }
    if is_htmx(request) and list_mode:
        return rows_response(request, mode=list_mode)
    return render(
        request,
        "contacts/partials/_bulk_bar.html",
        {
            "selected_count": len(mode_selected),
            "mode": list_mode,
            "bulk_form": BulkActionForm(user=request.user, list_mode=list_mode),
            "show_clear": False,
        },
    )


@login_required
@require_POST
def selection_clear(request):
    set_selected_ids(request, [])
    list_mode = request_list_mode(request, default="active")
    if is_htmx(request) and list_mode:
        return rows_response(request, mode=list_mode)
    if list_mode == "archive":
        return redirect("contacts:archive")
    if list_mode == "favorites":
        return redirect("contacts:favorites")
    return redirect("contacts:list")


@login_required
@require_POST
def selection_page(request):
    current = selected_ids(request)
    page_ids = set(request.POST.getlist("contact_ids"))
    owned_page_ids = {
        str(pk)
        for pk in Contact.objects.for_user(request.user)
        .filter(pk__in=page_ids)
        .values_list("pk", flat=True)
    }
    if request.POST.get("selected") == "true":
        current |= owned_page_ids
    else:
        current -= owned_page_ids
    set_selected_ids(request, current)
    list_mode = request_list_mode(request, default="active")
    if is_htmx(request):
        return rows_response(request, mode=list_mode)
    if list_mode == "archive":
        return redirect("contacts:archive")
    if list_mode == "favorites":
        return redirect("contacts:favorites")
    return redirect("contacts:list")


@login_required
@require_POST
def bulk_action(request):
    list_mode = request_list_mode(request, default="active")
    prune_selected_ids(request)
    form = BulkActionForm(
        request.POST,
        user=request.user,
        list_mode=list_mode,
    )
    current = selected_ids(request)
    contacts = list(selected_contacts_for_mode(request.user, current, list_mode))
    if form.is_valid():
        if not contacts:
            messages.warning(request, "No selected contacts match this view.")
        else:
            action = form.cleaned_data["action"]
            try:
                if action == "archive":
                    for contact in contacts:
                        contact.soft_delete()
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            len(contacts),
                            "%(count)s contact moved to archive.",
                            "%(count)s contacts moved to archive.",
                        ),
                    )
                elif action == "delete":
                    count = len(contacts)
                    Contact.objects.for_user(request.user).filter(
                        pk__in=[contact.pk for contact in contacts]
                    ).delete()
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            count,
                            "%(count)s contact permanently deleted.",
                            "%(count)s contacts permanently deleted.",
                        ),
                    )
                elif action == "restore":
                    for contact in contacts:
                        contact.restore()
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            len(contacts),
                            "%(count)s contact restored.",
                            "%(count)s contacts restored.",
                        ),
                    )
                elif action == "unfavorite":
                    count = len(contacts)
                    Contact.objects.for_user(request.user).filter(
                        pk__in=[contact.pk for contact in contacts]
                    ).update(is_favorite=False, updated_at=timezone.now())
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            count,
                            "%(count)s contact removed from favorites.",
                            "%(count)s contacts removed from favorites.",
                        ),
                    )
                elif action == "add_group":
                    form.cleaned_data["group"].contacts.add(*contacts)
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            len(contacts),
                            "%(count)s contact added to group.",
                            "%(count)s contacts added to group.",
                        ),
                    )
                elif action == "add_tag":
                    form.cleaned_data["tag"].contacts.add(*contacts)
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            len(contacts),
                            "Tag applied to %(count)s contact.",
                            "Tag applied to %(count)s contacts.",
                        ),
                    )
                elif action == "remove_tag":
                    form.cleaned_data["tag"].contacts.remove(*contacts)
                    set_selected_ids(request, [])
                    messages.success(
                        request,
                        format_count_message(
                            len(contacts),
                            "Tag removed from %(count)s contact.",
                            "Tag removed from %(count)s contacts.",
                        ),
                    )
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    parts = []
                    for msgs in exc.message_dict.values():
                        if isinstance(msgs, (list, tuple)):
                            parts.extend(str(msg) for msg in msgs)
                        else:
                            parts.append(str(msgs))
                    message = "; ".join(parts)
                else:
                    message = "; ".join(getattr(exc, "messages", [str(exc)]))
                messages.error(request, message or "Bulk action failed.")
    else:
        messages.error(request, "Check the bulk action fields.")
    if is_htmx(request) and list_mode:
        return rows_response(request, mode=list_mode)
    if list_mode == "archive":
        return redirect("contacts:archive")
    if list_mode == "favorites":
        return redirect("contacts:favorites")
    return redirect("contacts:list")


@login_required
@require_http_methods(["GET", "POST"])
def csv_import(request):
    form = CSVImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        clear_import_errors(request)
        result = stream_import_contacts(request.user, form.cleaned_data["file"])
        if result.errors:
            set_import_errors(
                request,
                [
                    {"row_number": err.row_number, "data": err.data, "errors": err.errors}
                    for err in result.errors[:MAX_IMPORT_ERRORS]
                ],
            )
            if len(result.errors) > MAX_IMPORT_ERRORS:
                messages.warning(
                    request,
                    f"Only the first {MAX_IMPORT_ERRORS} import errors were saved to the report.",
                )
        else:
            clear_import_errors(request)
        if result.imported_count:
            messages.success(
                request,
                format_count_message(
                    result.imported_count,
                    "%(count)s contact imported.",
                    "%(count)s contacts imported.",
                ),
            )
        if result.failed_count:
            messages.error(
                request,
                format_count_message(
                    result.failed_count,
                    "%(count)s row failed validation.",
                    "%(count)s rows failed validation.",
                ),
            )
        for warning in result.warnings:
            messages.warning(request, warning)
    return render(request, "contacts/csv_import.html", {"form": form, "result": result})


@login_required
def csv_error_report(request):
    from .importers import RowError

    raw_errors = get_import_errors(request)
    if not raw_errors:
        raise Http404("No import error report is available.")
    errors = [
        RowError(item["row_number"], item.get("data", {}), item.get("errors", {}))
        for item in raw_errors
    ]
    response = StreamingHttpResponse(error_report_rows(errors), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="address-book-import-errors.csv"'
    return response


@login_required
def csv_export(request):
    queryset = export_queryset(request, request.GET.get("mode", "active"))
    response = StreamingHttpResponse(csv_contact_rows(queryset), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="contacts.csv"'
    return response


@login_required
def vcard_export_one(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    response = HttpResponse(contact_to_vcard(contact), content_type="text/vcard")
    response["Content-Disposition"] = f'attachment; filename="contact-{contact.pk}.vcf"'
    return response


@login_required
def vcard_export_bulk(request):
    queryset = export_queryset(request, request.GET.get("mode", "active"))
    response = StreamingHttpResponse(vcards_for_contacts(queryset), content_type="text/vcard")
    response["Content-Disposition"] = 'attachment; filename="contacts.vcf"'
    return response
