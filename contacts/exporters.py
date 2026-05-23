"""CSV and vCard export helpers.

CSV export/import covers primary scalar contact fields only — not groups, tags,
or secondary phone/email rows. See docs/REPORT.md.
"""

import csv

from .csv_utils import CsvEcho
from .models import Email, Phone


Echo = CsvEcho


PHONE_VCARD_TYPES = {
    Phone.MOBILE: "CELL",
    Phone.WORK: "WORK",
    Phone.HOME: "HOME",
}


def csv_contact_rows(queryset):
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
            "Favorite",
            "Archived",
            "Notes",
        ]
    )
    for contact in queryset.iterator(chunk_size=500):
        yield writer.writerow(
            [
                contact.first_name,
                contact.last_name,
                contact.email,
                contact.phone,
                contact.company,
                contact.job_title,
                contact.birthday.isoformat() if contact.birthday else "",
                "yes" if contact.is_favorite else "no",
                "yes" if contact.is_archived else "no",
                contact.notes,
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


def contact_to_vcard(contact):
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{escape_vcard(contact.last_name)};{escape_vcard(contact.first_name)};;;",
        f"FN:{escape_vcard(contact.display_name)}",
    ]
    if contact.company:
        lines.append(f"ORG:{escape_vcard(contact.company)}")
    if contact.job_title:
        lines.append(f"TITLE:{escape_vcard(contact.job_title)}")
    for email in contact.emails.all():
        lines.append(format_vcard_email(email.address, email.label))
    if contact.email and not contact.emails.exists():
        lines.append(format_vcard_email(contact.email, Email.OTHER))
    for phone in contact.phones.all():
        lines.append(format_vcard_phone(phone.number, phone.label))
    if contact.phone and not contact.phones.exists():
        lines.append(format_vcard_phone(contact.phone, Phone.MOBILE))
    if contact.birthday:
        lines.append(f"BDAY:{contact.birthday.isoformat()}")
    if contact.notes:
        lines.append(f"NOTE:{escape_vcard(contact.notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


def vcards_for_contacts(queryset):
    for contact in queryset.prefetch_related("phones", "emails").iterator(chunk_size=250):
        yield contact_to_vcard(contact)
