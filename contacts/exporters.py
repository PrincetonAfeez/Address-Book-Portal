import csv


class Echo:
    def write(self, value):
        return value


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
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_line(line, limit=75):
    if len(line) <= limit:
        return line
    parts = [line[:limit]]
    rest = line[limit:]
    while rest:
        parts.append(" " + rest[: limit - 1])
        rest = rest[limit - 1 :]
    return "\r\n".join(parts)


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
        lines.append(f"EMAIL;TYPE={email.label.upper()}:{escape_vcard(email.address)}")
    if contact.email and not contact.emails.exists():
        lines.append(f"EMAIL;TYPE=OTHER:{escape_vcard(contact.email)}")
    for phone in contact.phones.all():
        lines.append(f"TEL;TYPE={phone.label.upper()}:{escape_vcard(phone.number)}")
    if contact.phone and not contact.phones.exists():
        lines.append(f"TEL;TYPE=MOBILE:{escape_vcard(contact.phone)}")
    if contact.birthday:
        lines.append(f"BDAY:{contact.birthday.isoformat()}")
    if contact.notes:
        lines.append(f"NOTE:{escape_vcard(contact.notes)}")
    lines.append("END:VCARD")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


def vcards_for_contacts(queryset):
    for contact in queryset.prefetch_related("phones", "emails").iterator(chunk_size=250):
        yield contact_to_vcard(contact)
