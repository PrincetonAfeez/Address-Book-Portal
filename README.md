# Address Book Portal

A Django 5 address book with server-rendered templates, HTMX interactions, per-user contact ownership, CSV import/export, vCard export, and soft archive behavior.

## Stack

- Python 3.12+ (`pyproject.toml`)
- Django 5
- Django templates + HTMX
- Tailwind CSS via CDN
- SQLite for development
- PostgreSQL for production
- WhiteNoise for static files in production

## Local Setup

Dependencies are defined in [`pyproject.toml`](pyproject.toml). Use an editable install so pytest and coverage pick up project settings from the same file.

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata seed_data
python manage.py runserver
```

Production-only install (no test tools):

```powershell
pip install -r requirements.txt
```

The seed user is `demo` with password `demo-password`.

`manage.py` defaults to `config.settings.dev`. Signup is at `/accounts/signup/`.

## Useful Commands

```powershell
python manage.py test
pytest
coverage run manage.py test
coverage report
python manage.py createsuperuser
python manage.py collectstatic
```

**Test suite:** 162 tests (all passing). **Line coverage:** 96%+ on `contacts` + `config` — see [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [Project report (limitations & future work)](docs/REPORT.md)
- [Requirements traceability matrix](docs/TRACEABILITY.md)
- [Testing & coverage](docs/TESTING.md)
- [ADR 0001 — HTMX over SPA](docs/adr/0001-htmx-over-spa.md)
- [ADR 0002 — Hand-rolled phone & vCard](docs/adr/0002-hand-rolled-phone-and-vcard.md)
- [ADR 0003 — Per-user ownership over RBAC](docs/adr/0003-per-user-ownership-over-rbac.md)
- [ADR 0004 — Scalar vs related contact fields](docs/adr/0004-scalar-and-related-contact-fields.md)

## Environment Variables

- `DJANGO_SECRET_KEY`: required in production.
- `DJANGO_DEBUG`: `True` for local development.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames.
- `DJANGO_TIME_ZONE`: timezone name (default `America/Los_Angeles`).
- `DATABASE_URL`: PostgreSQL URL for Railway or another host.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated HTTPS origins.
- `DJANGO_SERVE_MEDIA`: set `True` in production for small deployments (Railway ephemeral disk).
- `DJANGO_EMAIL_BACKEND`: override mail backend (console in dev).
- `DJANGO_DEFAULT_FROM_EMAIL`: from address for password reset mail.

## Deployment Notes

Set `DJANGO_SETTINGS_MODULE=config.settings.prod` in production (already the default in `config/wsgi.py`). Railway can use the included `railway.json` start command. Configure at minimum:

- `DJANGO_SECRET_KEY`
- `DATABASE_URL`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SERVE_MEDIA=True` if you want uploaded photos served by Django

For password reset email in production, configure your SMTP settings via Django's email environment variables or a provider backend.

## Project Notes

The core ownership rule lives in `OwnedManager.for_user()` and `get_for_user_or_404()`, so views ask the model layer for scoped data instead of open-coding owner filters each time. Phone validation and vCard generation are intentionally hand-rolled to keep dependencies minimal.

Bulk **Archive** soft-deletes contacts. Bulk **Delete permanently** is available from the archive view only.

Application logs are written to `logs/address_book.log` and the console.

## Pages

- `/` — dashboard
- `/contacts/` — contact list
- `/contacts/favorites/` — favorites
- `/contacts/archive/` — archived contacts
- `/organization/` — groups and tags
- `/import/` — CSV import
- `/accounts/signup/` — registration
- `/accounts/login/` — login
- `/accounts/password_reset/` — password reset
