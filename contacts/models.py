""" Models for the contacts app """

import logging
import uuid
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .validators import normalize_phone_number, validate_hex_color, validate_phone_number

logger = logging.getLogger(__name__)


def contact_photo_path(instance, filename):
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"contacts/user_{instance.owner_id}/photos/{uuid4().hex}{suffix}"


class OwnedQuerySet(models.QuerySet):
    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(owner=user)

    def active(self):
        return self.filter(is_archived=False) if hasattr(self.model, "is_archived") else self

    def archived(self):
        return self.filter(is_archived=True) if hasattr(self.model, "is_archived") else self

    def favorites(self):
        if not hasattr(self.model, "is_favorite"):
            return self
        qs = self.filter(is_favorite=True)
        if hasattr(self.model, "is_archived"):
            qs = qs.filter(is_archived=False)
        return qs

    def search(self, query):
        if not query:
            return self
        return self.filter(
            models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(phone__icontains=query)
            | models.Q(company__icontains=query)
            | models.Q(phones__number__icontains=query)
            | models.Q(emails__address__icontains=query)
        ).distinct()


class OwnedManager(models.Manager.from_queryset(OwnedQuerySet)):
    def get_for_user_or_404(self, user, **kwargs):
        return get_object_or_404(self.for_user(user), **kwargs)


class Contact(models.Model):
    """Per-user contact record.

    Validation runs on ``save()`` via ``full_clean()``. ``QuerySet.update()`` and
    bulk SQL bypass model validation; portal code should use ``save()``,
    ``ContactForm``, or ``create_validated()`` instead.
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True, validators=[validate_phone_number])
    company = models.CharField(max_length=120, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    birthday = models.DateField(blank=True, null=True)
    photo = models.ImageField(upload_to=contact_photo_path, blank=True)
    is_favorite = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["last_name", "first_name", "-updated_at"]
        indexes = [
            models.Index(fields=["owner", "is_archived"]),
            models.Index(fields=["owner", "is_favorite"]),
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        parts = [self.first_name[:1], self.last_name[:1]]
        return "".join(part for part in parts if part).upper() or "?"

    def get_absolute_url(self):
        return reverse("contacts:detail", kwargs={"pk": self.pk})

    @property
    def photo_url(self):
        if not self.photo:
            return ""
        return reverse("contacts:photo", kwargs={"pk": self.pk})

    @property
    def display_phone(self):
        if self.phone:
            return self.phone
        mobile = self.phones.filter(label=Phone.MOBILE).first()
        if mobile:
            return mobile.number
        phone = self.phones.first()
        return phone.number if phone else ""

    @property
    def display_email(self):
        if self.email:
            return self.email
        email = self.emails.first()
        return email.address if email else ""

    def clean(self):
        self.first_name = (self.first_name or "").strip()
        if not self.first_name:
            raise ValidationError({"first_name": "First name is required."})
        if self.email:
            self.email = self.email.strip().lower()
        if self.phone:
            try:
                self.phone = normalize_phone_number(self.phone)
            except ValidationError as exc:
                raise ValidationError({"phone": exc.messages}) from exc

    @classmethod
    def create_validated(cls, **kwargs):
        contact = cls(**kwargs)
        contact.save()
        return contact

    def save(self, *args, **kwargs):
        resize_photo = kwargs.pop("resize_photo", False)
        update_fields = kwargs.get("update_fields")
        if self.phone and (update_fields is None or "phone" in update_fields):
            try:
                self.phone = normalize_phone_number(self.phone)
            except ValidationError as exc:
                raise ValidationError({"phone": exc.messages}) from exc
        if update_fields is None:
            self.full_clean()
        else:
            exclude = [
                field.name
                for field in self._meta.fields
                if field.name not in update_fields and field.name != "id"
            ]
            self.full_clean(exclude=exclude)
        super().save(*args, **kwargs)
        if self.photo and resize_photo:
            self._resize_photo()

    def _resize_photo(self):
        if not self.photo:
            return
        try:
            import io

            from django.core.files.base import ContentFile
            from PIL import Image

            with self.photo.open("rb") as photo_file:
                with Image.open(photo_file) as image:
                    image.thumbnail((800, 800))
                    image_format = image.format or "JPEG"
                    buffer = io.BytesIO()
                    image.save(buffer, format=image_format)
            buffer.seek(0)
            self.photo.save(self.photo.name, ContentFile(buffer.read()), save=False)
            super().save(update_fields=["photo"])
        except (OSError, ValueError) as exc:
            logger.warning("Photo resize failed for contact %s: %s", self.pk, exc)
            return

    def soft_delete(self):
        self.is_archived = True
        self.is_favorite = False
        self.save(update_fields=["is_archived", "is_favorite", "updated_at"])

    def restore(self):
        self.is_archived = False
        self.save(update_fields=["is_archived", "updated_at"])


class Phone(models.Model):
    MOBILE = "mobile"
    WORK = "work"
    HOME = "home"
    LABEL_CHOICES = [
        (MOBILE, "Mobile"),
        (WORK, "Work"),
        (HOME, "Home"),
    ]

    contact = models.ForeignKey(Contact, related_name="phones", on_delete=models.CASCADE)
    number = models.CharField(max_length=32, validators=[validate_phone_number])
    label = models.CharField(max_length=16, choices=LABEL_CHOICES, default=MOBILE)
    is_scalar_sync = models.BooleanField(
        default=False,
        help_text="Managed by Contact.phone via sync_primary_records().",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.get_label_display()}: {self.number}"

    def clean(self):
        if self.number:
            try:
                self.number = normalize_phone_number(self.number)
            except ValidationError as exc:
                raise ValidationError({"number": exc.messages}) from exc

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Email(models.Model):
    WORK = "work"
    HOME = "home"
    OTHER = "other"
    LABEL_CHOICES = [
        (WORK, "Work"),
        (HOME, "Home"),
        (OTHER, "Other"),
    ]

    contact = models.ForeignKey(Contact, related_name="emails", on_delete=models.CASCADE)
    address = models.EmailField()
    label = models.CharField(max_length=16, choices=LABEL_CHOICES, default=OTHER)
    is_scalar_sync = models.BooleanField(
        default=False,
        help_text="Managed by Contact.email via sync_primary_records().",
    )

    class Meta:
        ordering = ["id"]

    def clean(self):
        self.address = (self.address or "").strip().lower()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_label_display()}: {self.address}"


class Group(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    contacts = models.ManyToManyField(Contact, related_name="groups", blank=True)

    objects = OwnedManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", name="unique_group_per_owner_ci")
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.name:
            self.name = self.name.strip()
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#2563eb")
    contacts = models.ManyToManyField(Contact, related_name="tags", blank=True)

    objects = OwnedManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), "owner", name="unique_tag_per_owner_ci")
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.name:
            self.name = self.name.strip()
        validate_hex_color(self.color)
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
