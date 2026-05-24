""" Utils for the contacts app """

from datetime import date, timedelta

def birthday_in_year(birthday, year):
    try:
        return birthday.replace(year=year)
    except ValueError:
        return birthday.replace(year=year, day=28)


def next_birthday_on_or_after(birthday, today):
    for year in (today.year, today.year + 1):
        candidate = birthday_in_year(birthday, year)
        if candidate >= today:
            return candidate
    return None


def upcoming_birthdays(contacts, today=None, within_days=30):
    today = today or date.today()
    limit = today + timedelta(days=within_days)
    results = []
    for contact in contacts:
        if not contact.birthday:
            continue
        upcoming = next_birthday_on_or_after(contact.birthday, today)
        if upcoming and upcoming <= limit:
            results.append((upcoming, contact))
    return sorted(results, key=lambda item: item[0])
