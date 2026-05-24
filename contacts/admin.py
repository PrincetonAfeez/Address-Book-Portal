""" Admin for the contacts app """

from django.contrib import admin

from .forms import ContactForm
from .models import Contact, Email, Group, Phone, Tag

SYNC_WARNING = (
    "Portal edits sync the primary phone (mobile) and email (other) from scalar fields. "
    "Extra phone/email rows with those labels are replaced on save."
)


class OwnerScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "owner_id") and not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "contacts" and not request.user.is_superuser:
            kwargs["queryset"] = Contact.objects.for_user(request.user)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class PhoneInline(admin.TabularInline):
    model = Phone
    extra = 0


class EmailInline(admin.TabularInline):
    model = Email
    extra = 0


@admin.register(Contact)
class ContactAdmin(OwnerScopedAdmin):
    list_display = (
        "display_name",
        "owner",
        "email",
        "phone",
        "company",
        "is_favorite",
        "is_archived",
        "updated_at",
    )
    list_filter = ("is_favorite", "is_archived", "created_at", "updated_at")
    search_fields = ("first_name", "last_name", "email", "phone", "company")
    inlines = [PhoneInline, EmailInline]
    readonly_fields = ("sync_warning",)

    fieldsets = (
        (
            None,
            {
                "fields": ("sync_warning", "owner", "first_name", "last_name", "email", "phone"),
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "company",
                    "job_title",
                    "notes",
                    "birthday",
                    "photo",
                    "is_favorite",
                    "is_archived",
                ),
            },
        ),
    )

    @admin.display(description="Primary-field sync")
    def sync_warning(self, obj):
        return SYNC_WARNING

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        return tuple(
            (
                title,
                {
                    **options,
                    "fields": tuple(f for f in options["fields"] if f != "owner"),
                },
            )
            for title, options in fieldsets
        )

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "owner_id") and not obj.owner_id:
            obj.owner = request.user
        resize_photo = bool(form and "photo" in form.changed_data and obj.photo)
        obj.save(resize_photo=resize_photo)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        ContactForm(instance=form.instance, user=request.user).sync_primary_records(form.instance)


@admin.register(Group)
class GroupAdmin(OwnerScopedAdmin):
    list_display = ("name", "owner", "contact_count")
    search_fields = ("name",)
    list_filter = ("owner",)

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return self.list_filter
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if request.user.is_superuser:
            return fields
        return tuple(field for field in fields if field != "owner")

    def contact_count(self, obj):
        return obj.contacts.count()


@admin.register(Tag)
class TagAdmin(OwnerScopedAdmin):
    list_display = ("name", "owner", "color", "contact_count")
    search_fields = ("name",)
    list_filter = ("owner",)

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return self.list_filter
        return ()

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if request.user.is_superuser:
            return fields
        return tuple(field for field in fields if field != "owner")

    def contact_count(self, obj):
        return obj.contacts.count()


class RelatedContactAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(contact__owner=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contact" and not request.user.is_superuser:
            kwargs["queryset"] = Contact.objects.for_user(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(Phone, RelatedContactAdmin)
admin.site.register(Email, RelatedContactAdmin)
