import codecs
import csv
from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Contact, Email, Phone


COLUMN_ALIASES = {
    "first_name": {"first name", "firstname", "first_name", "given name"},
    "last_name": {"last name", "lastname", "last_name", "surname", "family name"},
    "email": {"email", "email address", "e-mail"},
    "phone": {"phone", "phone number", "mobile", "telephone"},
    "company": {"company", "organization", "org"},
    "job_title": {"job title", "title", "role"},
    "birthday": {"birthday", "birthdate", "date of birth"},
    "notes": {"notes", "note"},
}


@dataclass
class RowError:
    row_number: int
    data: dict
    errors: dict


@dataclass
class ImportResult:
    imported_count: int = 0
    errors: list[RowError] = field(default_factory=list)

    @property
    def failed_count(self):
        return len(self.errors)


def canonical_header(header):
    normalized = (header or "").strip().lower().replace("-", " ").replace("_", " ")
    compact = normalized.replace(" ", "")
    for target, variants in COLUMN_ALIASES.items():
        if normalized in variants or compact in {variant.replace(" ", "") for variant in variants}:
            return target
    return normalized.replace(" ", "_")


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValidationError("Use YYYY-MM-DD, MM/DD/YYYY, or MM/DD/YY.")


def decoded_csv_lines(uploaded_file):
    pending = ""
    for chunk in codecs.iterdecode(uploaded_file.chunks(), "utf-8-sig"):
        pending += chunk
        lines = pending.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            pending = lines.pop()
        else:
            pending = ""
        yield from lines
    if pending:
        yield pending


def stream_import_contacts(owner, uploaded_file):
    result = ImportResult()
    reader = csv.DictReader(decoded_csv_lines(uploaded_file))
    if not reader.fieldnames:
        result.errors.append(RowError(1, {}, {"file": "CSV is missing a header row."}))
        return result

    field_map = {field: canonical_header(field) for field in reader.fieldnames}

    for row_number, raw_row in enumerate(reader, start=2):
        row = {field_map[key]: (value or "").strip() for key, value in raw_row.items()}
        try:
            if not row.get("first_name"):
                raise ValidationError({"first_name": "First name is required."})
            birthday = parse_date(row.get("birthday"))
            contact = Contact(
                owner=owner,
                first_name=row.get("first_name", ""),
                last_name=row.get("last_name", ""),
                email=row.get("email", ""),
                phone=row.get("phone", ""),
                company=row.get("company", ""),
                job_title=row.get("job_title", ""),
                birthday=birthday,
                notes=row.get("notes", ""),
            )
            contact.full_clean()
            with transaction.atomic():
                contact.save()
                if contact.phone:
                    Phone.objects.create(contact=contact, number=contact.phone, label=Phone.MOBILE)
                if contact.email:
                    Email.objects.create(contact=contact, address=contact.email, label=Email.OTHER)
            result.imported_count += 1
        except ValidationError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    data=row,
                    errors=getattr(exc, "message_dict", {"row": exc.messages}),
                )
            )
    return result


def error_report_rows(errors):
    writer = csv.writer(_Echo())
    yield writer.writerow(["Row", "Field", "Error"])
    for error in errors:
        for field, messages in error.errors.items():
            if isinstance(messages, str):
                messages = [messages]
            for message in messages:
                yield writer.writerow([error.row_number, field, message])


class _Echo:
    def write(self, value):
        return value
