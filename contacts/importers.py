""" Importers for the contacts app """

import codecs
import csv
from dataclasses import dataclass, field
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from .csv_utils import CsvEcho
from .models import Contact, Email, Phone
from .validators import normalize_phone_number


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
    for column, messages in errors.items():
        if isinstance(messages, str):
            normalized[column] = [messages]
        elif isinstance(messages, (list, tuple)):
            normalized[column] = [str(message) for message in messages]
        else:
            normalized[column] = [str(messages)]
    return normalized


KNOWN_IMPORT_FIELDS = frozenset(COLUMN_ALIASES.keys())
MAX_IMPORT_ERRORS = 500


def unrecognized_headers(fieldnames):
    return [
        header
        for header in fieldnames
        if header and canonical_header(header) not in KNOWN_IMPORT_FIELDS
    ]


@dataclass
class ImportResult:
    imported_count: int = 0
    skipped_count: int = 0
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

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
    for header in fieldnames:
        if not header:
            continue
        canonical = canonical_header(header)
        if canonical in canonical_sources:
            raise ValidationError(
                {
                    "file": (
                        f"Duplicate columns map to '{canonical}': "
                        f"'{canonical_sources[canonical]}' and '{header}'."
                    )
                }
            )
        canonical_sources[canonical] = header
        field_map[header] = canonical
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


def duplicate_import_match(owner, email="", phone=""):
    email = (email or "").strip()
    if email:
        if Contact.objects.for_user(owner).filter(email__iexact=email).exists():
            return "email"
        if Email.objects.filter(contact__owner=owner, address__iexact=email).exists():
            return "email"
    phone = (phone or "").strip()
    if not phone:
        return None
    try:
        normalized = normalize_phone_number(phone)
    except ValidationError:
        return None
    if Contact.objects.for_user(owner).filter(phone=normalized).exists():
        return "phone"
    if Phone.objects.filter(contact__owner=owner, number=normalized).exists():
        return "phone"
    return None


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

        unknown = unrecognized_headers(reader.fieldnames)
        if unknown:
            result.warnings.append(
                "Ignored unrecognized columns: " + ", ".join(unknown) + "."
            )

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
                duplicate = duplicate_import_match(
                    owner,
                    email=row.get("email", ""),
                    phone=row.get("phone", ""),
                )
                if duplicate:
                    result.skipped_count += 1
                    result.warnings.append(
                        f"Row {row_number}: duplicate {duplicate} skipped."
                    )
                    continue
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
        for column, messages in error.errors.items():
            if isinstance(messages, str):
                messages = [messages]
            for message in messages:
                yield writer.writerow([error.row_number, column, message])

