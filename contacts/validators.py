import re

from django.core.exceptions import ValidationError


FORMAT_CHARS = str.maketrans("", "", " -.()")


def normalize_phone_number(value):
    if value in {None, ""}:
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    if re.search(r"[A-Za-z]", raw):
        raise ValidationError("Phone numbers cannot contain letters.")

    compact = raw.translate(FORMAT_CHARS)
    if compact.startswith("+"):
        digits = compact[1:]
        if "+" in digits or not digits.isdigit():
            raise ValidationError("Use digits after a single leading '+'.")
        if not re.fullmatch(r"[1-9]\d{7,14}", digits):
            raise ValidationError("Use E.164 format, such as +14155552671.")
        return f"+{digits}"

    if not compact.isdigit():
        raise ValidationError("Use digits, spaces, dashes, dots, or parentheses only.")

    if len(compact) == 10:
        return f"+1{compact}"

    if len(compact) == 11 and compact.startswith("1"):
        return f"+{compact}"

    raise ValidationError("Use a 10-digit US number or E.164 format.")


def validate_phone_number(value):
    normalize_phone_number(value)
