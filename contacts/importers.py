import codecs
import csv
from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from .csv_utils import CsvEcho
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

    def __post_init__(self):
        self.errors = normalize_field_errors(self.errors)


def normalize_field_errors(errors):
    normalized = {}
    for field, messages in errors.items():
        if isinstance(messages, str):
            normalized[field] = [messages]
        elif isinstance(messages, (list, tuple)):
            normalized[field] = [str(message) for message in messages]
        else:
            normalized[field] = [str(messages)]
    return normalized


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


def build_field_map(fieldnames):
    field_map = {}
    canonical_sources = {}
    for field in fieldnames:
        if not field:
            continue
        canonical = canonical_header(field)
        if canonical in canonical_sources:
            raise ValidationError(
                {
                    "file": (
                        f"Duplicate columns map to '{canonical}': "
                        f"'{canonical_sources[canonical]}' and '{field}'."
                    )
                }
            )
        canonical_sources[canonical] = field
        field_map[field] = canonical
    return field_map


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValidationError({"birthday": "Use YYYY-MM-DD, MM/DD/YYYY, or MM/DD/YY."})


def decoded_csv_lines(uploaded_file):
    pending = ""
    for chunk in codecs.iterdecode(uploaded_file.chunks(), "utf-8-sig"):
        pending += chunk
        while True:
            crlf = pending.find("\r\n")
            if crlf != -1:
                yield pending[: crlf + 2]
                pending = pending[crlf + 2 :]
                continue
            lf = pending.find("\n")
            if lf != -1:
                yield pending[: lf + 1]
                pending = pending[lf + 1 :]
                continue
            if pending.endswith("\r"):
                break
            cr = pending.find("\r")
            if cr != -1:
                yield pending[: cr + 1]
                pending = pending[cr + 1 :]
                continue
            break
    if pending:
        yield pending


def stream_import_contacts(owner, uploaded_file):
    result = ImportResult()
    try:
        reader = csv.DictReader(decoded_csv_lines(uploaded_file), restkey="__extra__")
        if not reader.fieldnames:
            result.errors.append(RowError(1, {}, {"file": "CSV is missing a header row."}))
            return result

        try:
            field_map = build_field_map(reader.fieldnames)
        except ValidationError as exc:
            result.errors.append(
                RowError(1, {}, getattr(exc, "message_dict", {"file": exc.messages}))
            )
            return result

        for row_number, raw_row in enumerate(reader, start=2):
            if raw_row.pop("__extra__", None) is not None:
                result.errors.append(
                    RowError(row_number, {}, {"row": "Too many columns."})
                )
                continue
            row = {
                field_map[key]: (value or "").strip()
                for key, value in raw_row.items()
                if key in field_map
            }
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
                errors = getattr(exc, "message_dict", None) or {"row": exc.messages}
                result.errors.append(
                    RowError(
                        row_number=row_number,
                        data=row,
                        errors=errors,
                    )
                )
    except UnicodeDecodeError:
        result.errors.append(RowError(1, {}, {"file": "CSV must be UTF-8 encoded."}))
    return result


def error_report_rows(errors):
    writer = csv.writer(CsvEcho())
    yield writer.writerow(["Row", "Field", "Error"])
    for error in errors:
        for field, messages in error.errors.items():
            if isinstance(messages, str):
                messages = [messages]
            for message in messages:
                yield writer.writerow([error.row_number, field, message])

