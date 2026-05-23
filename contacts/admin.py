from django.contrib import admin

from .forms import ContactForm
from .models import Contact, Email, Group, Phone, Tag


class PhoneInline(admin.TabularInline):
    model = Phone
    extra = 0


class EmailInline(admin.TabularInline):
    model = Email
    extra = 0


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ContactForm(instance=obj).sync_primary_records(obj)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "contact_count")
    search_fields = ("name",)
    list_filter = ("owner",)

    def contact_count(self, obj):
        return obj.contacts.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "color", "contact_count")
    search_fields = ("name",)
    list_filter = ("owner",)

    def contact_count(self, obj):
        return obj.contacts.count()


admin.site.register(Phone)
admin.site.register(Email)
