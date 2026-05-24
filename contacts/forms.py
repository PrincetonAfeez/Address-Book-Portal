""" Forms for the contacts app """

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Contact, Email, Group, Phone, Tag
from .validators import normalize_phone_number, validate_hex_color, validate_uploaded_photo

User = get_user_model()


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ContactForm(forms.ModelForm):
    first_name = forms.CharField(max_length=80, required=True)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "input", "size": 4}),
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "input", "size": 4}),
    )

    class Meta:
        model = Contact
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "company",
            "job_title",
            "birthday",
            "photo",
            "is_favorite",
            "notes",
        ]
        widgets = {
            "birthday": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["groups"].queryset = Group.objects.for_user(user)
            self.fields["tags"].queryset = Tag.objects.for_user(user)
        if self.instance.pk:
            self.fields["groups"].initial = self.instance.groups.all()
            self.fields["tags"].initial = self.instance.tags.all()

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        return normalize_phone_number(phone) if phone else ""

    def clean_first_name(self):
        name = self.cleaned_data.get("first_name", "").strip()
        if not name:
            raise forms.ValidationError("Enter a first name.")
        return name

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        try:
            return validate_uploaded_photo(photo)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def save(self, commit=True):
        instance = super().save(commit=False)
        resize_photo = "photo" in self.changed_data or not instance.pk
        if commit:
            instance.save(resize_photo=resize_photo and bool(instance.photo))
            self.sync_primary_records(instance)
            if self.user is not None:
                instance.groups.set(self.cleaned_data.get("groups", []))
                instance.tags.set(self.cleaned_data.get("tags", []))
        return instance

    def sync_primary_records(self, contact):
        synced_mobiles = contact.phones.filter(
            label=Phone.MOBILE,
            is_scalar_sync=True,
        ).order_by("pk")
        if contact.phone:
            primary = synced_mobiles.first()
            if not primary:
                match = contact.phones.filter(label=Phone.MOBILE, number=contact.phone).first()
                if match:
                    match.is_scalar_sync = True
                    match.save(update_fields=["is_scalar_sync"])
                    primary = match
            if primary:
                if primary.number != contact.phone:
                    primary.number = contact.phone
                    primary.save(update_fields=["number"])
                synced_mobiles.exclude(pk=primary.pk).delete()
            else:
                Phone.objects.create(
                    contact=contact,
                    number=contact.phone,
                    label=Phone.MOBILE,
                    is_scalar_sync=True,
                )
        else:
            synced_mobiles.delete()

        synced_others = contact.emails.filter(
            label=Email.OTHER,
            is_scalar_sync=True,
        ).order_by("pk")
        if contact.email:
            primary = synced_others.first()
            if not primary:
                match = contact.emails.filter(label=Email.OTHER, address=contact.email).first()
                if match:
                    match.is_scalar_sync = True
                    match.save(update_fields=["is_scalar_sync"])
                    primary = match
            if primary:
                if primary.address != contact.email:
                    primary.address = contact.email
                    primary.save(update_fields=["address"])
                synced_others.exclude(pk=primary.pk).delete()
            else:
                Email.objects.create(
                    contact=contact,
                    address=contact.email,
                    label=Email.OTHER,
                    is_scalar_sync=True,
                )
        else:
            synced_others.delete()


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a group name.")
        if self.user:
            qs = Group.objects.for_user(self.user).filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("You already have a group with this name.")
        return name


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a tag name.")
        if self.user:
            qs = Tag.objects.for_user(self.user).filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("You already have a tag with this name.")
        return name

    def clean(self):
        cleaned = super().clean()
        color = cleaned.get("color", "")
        if color:
            try:
                validate_hex_color(color)
            except ValidationError as exc:
                self.add_error("color", exc.messages[0])
        return cleaned


class CSVImportForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        if uploaded.size > 5 * 1024 * 1024:
            raise forms.ValidationError("CSV files are limited to 5 MB.")
        return uploaded


class BulkActionForm(forms.Form):
    ACTION_CHOICES = [
        ("archive", "Archive"),
        ("delete", "Delete permanently"),
        ("restore", "Restore"),
        ("unfavorite", "Remove from favorites"),
        ("add_group", "Add to group"),
        ("add_tag", "Add tag"),
        ("remove_tag", "Remove tag"),
    ]

    action = forms.ChoiceField(choices=ACTION_CHOICES)
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "input"}),
    )
    tag = forms.ModelChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "input"}),
    )

    def __init__(self, *args, user=None, list_mode="active", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].widget.attrs.update({"class": "input"})
        if list_mode == "archive":
            self.fields["action"].choices = [
                ("restore", "Restore"),
                ("delete", "Delete permanently"),
                ("add_group", "Add to group"),
                ("add_tag", "Add tag"),
                ("remove_tag", "Remove tag"),
            ]
        elif list_mode == "favorites":
            self.fields["action"].choices = [
                ("archive", "Archive"),
                ("unfavorite", "Remove from favorites"),
                ("add_group", "Add to group"),
                ("add_tag", "Add tag"),
                ("remove_tag", "Remove tag"),
            ]
        else:
            self.fields["action"].choices = [
                ("archive", "Archive"),
                ("add_group", "Add to group"),
                ("add_tag", "Add tag"),
                ("remove_tag", "Remove tag"),
            ]
        if user is not None:
            self.fields["group"].queryset = Group.objects.for_user(user)
            self.fields["tag"].queryset = Tag.objects.for_user(user)

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        if action == "add_group" and not cleaned.get("group"):
            self.add_error("group", "Choose a group.")
        if action in {"add_tag", "remove_tag"} and not cleaned.get("tag"):
            self.add_error("tag", "Choose a tag.")
        return cleaned
