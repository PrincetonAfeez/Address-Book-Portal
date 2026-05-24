"""CSV and vCard export helpers.

Primary-fields CSV export/import covers scalar contact columns only — not groups,
tags, favorite/archive flags, or secondary phone/email rows. See docs/REPORT.md.
"""

import base64
import csv
import mimetypes
from datetime import timezone as dt_timezone

from django.utils import timezone

from .csv_utils import CsvEcho
from .models import Email, Phone


Echo = CsvEcho
UTF8_BOM = "\ufeff"


PHONE_VCARD_TYPES = {
    Phone.MOBILE: "CELL",
    Phone.WORK: "WORK",
    Phone.HOME: "HOME",
}


DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def safe_csv_cell(value):
    text = str(value or "")
    return "'" + text if text.startswith(DANGEROUS_PREFIXES) else text


def csv_contact_rows(queryset):
    yield UTF8_BOM
    writer = csv.writer(Echo())
    yield writer.writerow(
        [
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Company",
            "Job Title",
            "Birthday",
            "Notes",
        ]
    )
    for contact in queryset.prefetch_related("phones", "emails").iterator(chunk_size=500):
        yield writer.writerow(
            [
                safe_csv_cell(contact.first_name),
                safe_csv_cell(contact.last_name),
                safe_csv_cell(contact.display_email),
                safe_csv_cell(contact.display_phone),
                safe_csv_cell(contact.company),
                safe_csv_cell(contact.job_title),
                contact.birthday.isoformat() if contact.birthday else "",
                safe_csv_cell(contact.notes),
            ]
        )


def escape_vcard(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _utf8_chunk(data):
    while data:
        try:
            data.decode("utf-8")
            return data
        except UnicodeDecodeError:
            data = data[:-1]
    return b""


def fold_line(line, limit=75):
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    parts = []
    pos = 0
    first = True
    while pos < len(encoded):
        max_len = limit if first else limit - 1
        chunk = _utf8_chunk(encoded[pos : pos + max_len])
        if not chunk:
            break
        segment = chunk.decode("utf-8")
        parts.append(segment if first else " " + segment)
        pos += len(chunk)
        first = False
    return "\r\n".join(parts)


def format_vcard_phone(number, label):
    vtype = PHONE_VCARD_TYPES.get(label, label.upper())
    return f"TEL;TYPE={vtype}:{escape_vcard(number)}"


def format_vcard_email(address, label):
    if label == Email.OTHER:
        return f"EMAIL:{escape_vcard(address)}"
    return f"EMAIL;TYPE={label.upper()}:{escape_vcard(address)}"


def _vcard_photo_line(contact):
    if not contact.photo:
        return None
    try:
        with contact.photo.open("rb") as photo_file:
            encoded = base64.b64encode(photo_file.read()).decode("ascii")
    except OSError:
        return None
    content_type, _ = mimetypes.guess_type(contact.photo.name)
    photo_type = (content_type or "image/jpeg").split("/")[-1].upper()
    if photo_type == "JPG":
        photo_type = "JPEG"
    return f"PHOTO;ENCODING=b;TYPE={photo_type}:{encoded}"


def contact_to_vcard(contact):
    rev = timezone.localtime(contact.updated_at, dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        "PRODID:-//Address Book Portal//EN",
        f"UID:{contact.uuid}@address-book-portal",
        f"REV:{rev}",
        f"N:{escape_vcard(contact.last_name)};{escape_vcard(contact.first_name)};;;",
        f"FN:{escape_vcard(contact.display_name)}",
    ]
    if contact.company:
        lines.append(f"ORG:{escape_vcard(contact.company)}")
    if contact.job_title:
        lines.append(f"TITLE:{escape_vcard(contact.job_title)}")
    exported_emails = set()
    for email in contact.emails.all():
        lines.append(format_vcard_email(email.address, email.label))
        exported_emails.add(email.address)
    if contact.email and contact.email not in exported_emails:
        lines.append(format_vcard_email(contact.email, Email.OTHER))
    exported_phones = set()
    for phone in contact.phones.all():
        lines.append(format_vcard_phone(phone.number, phone.label))
        exported_phones.add(phone.number)
    if contact.phone and contact.phone not in exported_phones:
        lines.append(format_vcard_phone(contact.phone, Phone.MOBILE))
    if contact.birthday:
        lines.append(f"BDAY:{contact.birthday.isoformat()}")
    if contact.notes:
        lines.append(f"NOTE:{escape_vcard(contact.notes)}")
    photo_line = _vcard_photo_line(contact)
    if photo_line:
        lines.append(photo_line)
    lines.append("END:VCARD")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


def vcards_for_contacts(queryset):
    for contact in queryset.prefetch_related("phones", "emails").iterator(chunk_size=250):
        yield contact_to_vcard(contact)
