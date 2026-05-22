from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from contacts.validators import normalize_phone_number, validate_phone_number


class PhoneValidatorTests(SimpleTestCase):
    def test_normalizes_common_valid_numbers(self):
        cases = {
            "(415) 555-2671": "+14155552671",
            "1.415.555.2671": "+14155552671",
            "+442079460958": "+442079460958",
            "": "",
            None: "",
            "   ": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone_number(raw), expected)

    def test_rejects_invalid_numbers(self):
        for raw in ["555", "+012345678", "415-CALL-NOW", "++14155552671", "+1+2", "abc"]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError):
                    normalize_phone_number(raw)

    def test_rejects_non_digit_characters(self):
        with self.assertRaises(ValidationError):
            normalize_phone_number("415-555-ABCD")

    def test_rejects_invalid_e164_length(self):
        with self.assertRaises(ValidationError):
            normalize_phone_number("+1234567")

    def test_validate_phone_number_delegates(self):
        validate_phone_number("(415) 555-2671")
