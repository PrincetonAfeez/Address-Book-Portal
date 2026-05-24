""" Validators for the contacts app """

import re

from django.core.exceptions import ValidationError

ALLOWED_PHOTO_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_DIMENSION = 8000
MIN_PHOTO_DIMENSION = 1
MAX_PHOTO_PIXELS = MAX_PHOTO_DIMENSION * MAX_PHOTO_DIMENSION


FORMAT_CHARS = str.maketrans("", "", " -.()")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


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


def validate_hex_color(value):
    if not HEX_COLOR_RE.match(value or ""):
        raise ValidationError("Use a hex color like #2563eb.")


def validate_uploaded_photo(photo):
    if not photo or not hasattr(photo, "read"):
        return photo

    size = getattr(photo, "size", 0)
    if size > MAX_PHOTO_BYTES:
        raise ValidationError("Photos are limited to 5 MB.")

    content_type = getattr(photo, "content_type", "")
    if content_type and content_type not in ALLOWED_PHOTO_CONTENT_TYPES:
        raise ValidationError("Upload a JPEG, PNG, GIF, or WebP image.")

    try:
        from PIL import Image

        photo.seek(0)
        with Image.open(photo) as image:
            image.verify()
        photo.seek(0)
        with Image.open(photo) as image:
            width, height = image.size
            if width < MIN_PHOTO_DIMENSION or height < MIN_PHOTO_DIMENSION:
                raise ValidationError("Image dimensions are too small.")
            if width > MAX_PHOTO_DIMENSION or height > MAX_PHOTO_DIMENSION:
                raise ValidationError(
                    f"Image dimensions cannot exceed {MAX_PHOTO_DIMENSION} pixels."
                )
            if width * height > MAX_PHOTO_PIXELS:
                raise ValidationError("Image pixel count is too large.")
        photo.seek(0)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Upload a valid image file.") from exc

    return photo
