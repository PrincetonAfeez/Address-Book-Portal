""" Signals for the contacts app """

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models.signals import m2m_changed, pre_delete, pre_save
from django.dispatch import receiver

from .models import Contact, Group, Tag
from .session_selection import (
    IMPORT_ERRORS_USER_KEY,
    SESSION_USER_KEY,
    bind_import_errors_user,
    bind_selection_user,
    clear_import_errors,
    clear_selected_ids,
)


def _validate_contact_ownership(owner_id, pk_set):
    if not pk_set:
        return
    invalid = Contact.all_objects.filter(pk__in=pk_set).exclude(owner=owner_id)
    if invalid.exists():
        raise ValidationError("Cannot link contacts owned by another user.")


def _validate_group_ownership(owner_id, pk_set):
    if not pk_set:
        return
    invalid = Group.all_objects.filter(pk__in=pk_set).exclude(owner=owner_id)
    if invalid.exists():
        raise ValidationError("Cannot link groups owned by another user.")


def _validate_tag_ownership(owner_id, pk_set):
    if not pk_set:
        return
    invalid = Tag.all_objects.filter(pk__in=pk_set).exclude(owner=owner_id)
    if invalid.exists():
        raise ValidationError("Cannot link tags owned by another user.")


@receiver(m2m_changed, sender=Group.contacts.through)
def validate_group_contacts(sender, instance, action, pk_set, reverse, **kwargs):
    if action == "pre_add":
        if reverse:
            _validate_group_ownership(instance.owner_id, pk_set)
        else:
            _validate_contact_ownership(instance.owner_id, pk_set)


@receiver(m2m_changed, sender=Tag.contacts.through)
def validate_tag_contacts(sender, instance, action, pk_set, reverse, **kwargs):
    if action == "pre_add":
        if reverse:
            _validate_tag_ownership(instance.owner_id, pk_set)
        else:
            _validate_contact_ownership(instance.owner_id, pk_set)


@receiver(user_logged_in)
def bind_session_on_login(sender, request, user, **kwargs):
    bind_selection_user(request, user)
    bind_import_errors_user(request, user)


@receiver(user_logged_out)
def clear_session_on_logout(sender, request, user, **kwargs):
    clear_selected_ids(request)
    clear_import_errors(request)
    if request and hasattr(request, "session"):
        request.session.pop(SESSION_USER_KEY, None)
        request.session.pop(IMPORT_ERRORS_USER_KEY, None)
        request.session.modified = True


@receiver(pre_delete, sender=Contact)
def delete_contact_photo_file(sender, instance, **kwargs):
    if instance.photo:
        instance.photo.delete(save=False)


@receiver(pre_save, sender=Contact)
def delete_replaced_contact_photo(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = Contact.all_objects.filter(pk=instance.pk).values_list("photo", flat=True).first()
    new_name = instance.photo.name if instance.photo else ""
    if previous and previous != new_name:
        default_storage.delete(previous)
