""" Test utils for the contacts app """

from datetime import date

from django.test import SimpleTestCase

from contacts.utils import birthday_in_year, next_birthday_on_or_after, upcoming_birthdays


class BirthdayUtilsTests(SimpleTestCase):
    def test_birthday_in_year_handles_leap_day(self):
        leap_birthday = date(2020, 2, 29)

        self.assertEqual(birthday_in_year(leap_birthday, 2025), date(2025, 2, 28))
        self.assertEqual(birthday_in_year(leap_birthday, 2024), date(2024, 2, 29))

    def test_next_birthday_on_or_after_uses_following_year_when_needed(self):
        birthday = date(1990, 12, 31)
        today = date(2026, 5, 22)

        self.assertEqual(next_birthday_on_or_after(birthday, today), date(2026, 12, 31))

    def test_upcoming_birthdays_includes_leap_day_contacts(self):
        class Contact:
            def __init__(self, birthday):
                self.birthday = birthday

        contacts = [Contact(date(2020, 2, 29))]
        today = date(2025, 2, 1)

        results = upcoming_birthdays(contacts, today=today, within_days=60)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], date(2025, 2, 28))

    def test_upcoming_birthdays_skips_contacts_without_birthday(self):
        class Contact:
            def __init__(self, birthday):
                self.birthday = birthday

        contacts = [Contact(None)]
        self.assertEqual(upcoming_birthdays(contacts, today=date(2025, 1, 1)), [])

    def test_next_birthday_on_or_after_returns_none_for_impossible_year(self):
        birthday = date(1990, 1, 1)
        # today far in future - still should return a date within 2 years
        today = date(2090, 12, 31)
        self.assertEqual(next_birthday_on_or_after(birthday, today), date(2091, 1, 1))
