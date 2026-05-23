from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import Contact, Group, Tag


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
