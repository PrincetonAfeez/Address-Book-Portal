from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .exporters import contact_to_vcard, csv_contact_rows, vcards_for_contacts
from .forms import BulkActionForm, CSVImportForm, ContactForm, GroupForm, SignupForm, TagForm
from .importers import error_report_rows, stream_import_contacts
from .models import Contact, Group, Tag
from .utils import upcoming_birthdays


SELECTED_SESSION_KEY = "selected_contact_ids"
SORTS = {
    "name": ("last_name", "first_name"),
    "company": ("company", "last_name", "first_name"),
    "created": ("created_at",),
    "updated": ("updated_at",),
}


def signup(request):
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


def request_list_mode(request, default=""):
    return request.POST.get("list_mode") or request.GET.get("list_mode") or default


def selected_ids(request):
    return set(request.session.get(SELECTED_SESSION_KEY, []))


def set_selected_ids(request, ids):
    request.session[SELECTED_SESSION_KEY] = sorted({str(contact_id) for contact_id in ids})
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


def htmx_redirect(url):
    response = HttpResponse(status=204)
    response["HX-Redirect"] = url
    return response


def selected_contacts_for_mode(user, selected, list_mode):
    qs = Contact.objects.for_user(user).filter(pk__in=selected)
    if list_mode == "archive":
        return qs.archived()
    if list_mode == "favorites":
        return qs.active().favorites()
    return qs.active()


def htmx_list_or_redirect(request, *, redirect_to, refresh_modes=None):
    if not is_htmx(request):
        return None
    list_mode = request_list_mode(request)
    if list_mode and list_mode not in (refresh_modes or set()):
        return rows_response(request, mode=list_mode)
    return htmx_redirect(redirect_to)


def base_contact_queryset(request, mode="active"):
    qs = (
        Contact.objects.for_user(request.user)
        .prefetch_related("groups", "tags", "phones", "emails")
        .distinct()
    )
    if mode == "archive":
        qs = qs.archived()
    else:
        qs = qs.active()
    if mode == "favorites":
        qs = qs.favorites()

    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group")
    tag_id = request.GET.get("tag")

    qs = qs.search(query)
    if group_id and Group.objects.for_user(request.user).filter(pk=group_id).exists():
        qs = qs.filter(groups__id=group_id)
    if tag_id and Tag.objects.for_user(request.user).filter(pk=tag_id).exists():
        qs = qs.filter(tags__id=tag_id)

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
    selected = prune_selected_ids(request)
    page_contact_ids = {str(contact.id) for contact in page_obj.object_list}
    return {
        "mode": mode,
        "list_mode": mode,
        "contacts": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "groups": Group.objects.for_user(request.user).order_by("name"),
        "tags": Tag.objects.for_user(request.user).order_by("name"),
        "selected_ids": selected,
        "selected_count": len(selected),
        "page_all_selected": bool(page_contact_ids and page_contact_ids <= selected),
        "bulk_form": BulkActionForm(user=request.user, list_mode=mode),
        "sort": request.GET.get("sort", "name"),
        "direction": request.GET.get("dir", "asc"),
        "query": request.GET.get("q", ""),
        "is_htmx": is_htmx(request),
    }


def rows_response(request, mode="active", status=200):
    context = list_context(request, mode)
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
    today = date.today()

    context = {
        "total_contacts": contacts.count(),
        "total_groups": Group.objects.for_user(request.user).count(),
        "total_tags": Tag.objects.for_user(request.user).count(),
        "recent_additions": contacts.filter(created_at__date__gte=today - timedelta(days=7))[:5],
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
    group_form = GroupForm(prefix="group", user=request.user)
    tag_form = TagForm(prefix="tag", user=request.user)

    if request.method == "POST" and request.POST.get("kind") == "group":
        group_form = GroupForm(request.POST, prefix="group", user=request.user)
        if group_form.is_valid():
            group = group_form.save(commit=False)
            group.owner = request.user
            group.save()
            messages.success(request, f"{group.name} group created.")
            return redirect("contacts:organization")

    if request.method == "POST" and request.POST.get("kind") == "tag":
        tag_form = TagForm(request.POST, prefix="tag", user=request.user)
        if tag_form.is_valid():
            tag = tag_form.save(commit=False)
            tag.owner = request.user
            tag.full_clean()
            tag.save()
            messages.success(request, f"{tag.name} tag created.")
            return redirect("contacts:organization")

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
@require_http_methods(["GET", "POST"])
def contact_create(request):
    list_mode = request_list_mode(request)
    form = ContactForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.owner = request.user
        contact.full_clean()
        contact.save()
        form.sync_primary_records(contact)
        messages.success(request, f"{contact.display_name} was added.")
        htmx_response = htmx_list_or_redirect(
            request,
            redirect_to=contact.get_absolute_url(),
            refresh_modes={"archive"},
        )
        if htmx_response:
            return htmx_response
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
    form = ContactForm(request.POST or None, request.FILES or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        contact = form.save()
        form.sync_primary_records(contact)
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
    messages.success(request, f"{contact.display_name} moved to archive.")
    list_mode = request_list_mode(request, default="active")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:list"),
    )
    if htmx_response:
        return htmx_response
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
    messages.success(request, f"{contact.display_name} was restored.")
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:archive"),
    )
    if htmx_response:
        return htmx_response
    return redirect("contacts:archive")


@login_required
@require_POST
def contact_toggle_favorite(request, pk):
    contact = Contact.objects.get_for_user_or_404(request.user, pk=pk)
    contact.is_favorite = not contact.is_favorite
    contact.save(update_fields=["is_favorite", "updated_at"])
    htmx_response = htmx_list_or_redirect(
        request,
        redirect_to=reverse("contacts:list"),
    )
    if htmx_response:
        return htmx_response
    list_mode = request_list_mode(request, default="active")
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
    current = prune_selected_ids(request)
    list_mode = request_list_mode(request)
    if is_htmx(request) and list_mode:
        return rows_response(request, mode=list_mode)
    return render(
        request,
        "contacts/partials/_selection_bar.html",
        {
            "selected_count": len(current),
            "bulk_form": BulkActionForm(
                user=request.user,
                list_mode=request_list_mode(request, default="active"),
            ),
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
    if request.POST.get("selected") == "true":
        current |= page_ids
    else:
        current -= page_ids
    set_selected_ids(request, current)
    list_mode = request_list_mode(request, default="active")
    return rows_response(request, mode=list_mode)


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
    contacts = selected_contacts_for_mode(request.user, current, list_mode)
    if form.is_valid():
        action = form.cleaned_data["action"]
        if action == "archive":
            for contact in contacts:
                contact.soft_delete()
            set_selected_ids(request, [])
            messages.success(request, "Selected contacts moved to archive.")
        elif action == "delete":
            count = contacts.count()
            contacts.delete()
            set_selected_ids(request, [])
            messages.success(request, f"{count} contacts permanently deleted.")
        elif action == "add_group":
            form.cleaned_data["group"].contacts.add(*contacts)
            messages.success(request, "Contacts added to group.")
        elif action == "add_tag":
            form.cleaned_data["tag"].contacts.add(*contacts)
            messages.success(request, "Tag applied to contacts.")
        elif action == "remove_tag":
            form.cleaned_data["tag"].contacts.remove(*contacts)
            messages.success(request, "Tag removed from contacts.")
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
        result = stream_import_contacts(request.user, form.cleaned_data["file"])
        request.session["last_import_errors"] = [
            {"row_number": err.row_number, "data": err.data, "errors": err.errors}
            for err in result.errors
        ]
        request.session.modified = True
        if result.imported_count:
            messages.success(request, f"{result.imported_count} contacts imported.")
        if result.failed_count:
            messages.error(request, f"{result.failed_count} rows failed validation.")
    return render(request, "contacts/csv_import.html", {"form": form, "result": result})


@login_required
def csv_error_report(request):
    from .importers import RowError

    raw_errors = request.session.get("last_import_errors")
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
    queryset = base_contact_queryset(request, request.GET.get("mode", "active"))
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
    queryset = base_contact_queryset(request, request.GET.get("mode", "active"))
    response = StreamingHttpResponse(vcards_for_contacts(queryset), content_type="text/vcard")
    response["Content-Disposition"] = 'attachment; filename="contacts.vcf"'
    return response
