from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Contact, Email, Group, Phone, Tag
from .validators import normalize_phone_number, validate_hex_color

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].widget = forms.ClearableFileInput()

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        return normalize_phone_number(phone) if phone else ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        resize_photo = "photo" in self.changed_data or not instance.pk
        if commit:
            instance.save(resize_photo=resize_photo and bool(instance.photo))
            self.sync_primary_records(instance)
        return instance

    def sync_primary_records(self, contact):
        contact.phones.filter(label=Phone.MOBILE).delete()
        if contact.phone:
            Phone.objects.create(contact=contact, number=contact.phone, label=Phone.MOBILE)

        contact.emails.filter(label=Email.OTHER).delete()
        if contact.email:
            Email.objects.create(contact=contact, address=contact.email, label=Email.OTHER)


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
                ("delete", "Delete permanently"),
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
