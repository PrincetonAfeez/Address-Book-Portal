# Architecture Decision Record
## App — Address Book Portal
**Contact Management Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Contact Management group requires a Django address book that supports authenticated personal contact management, not a public single-user demo. The application must let each user manage private contacts, mark favorites, archive and restore records, organize contacts with groups and tags, import/export CSV, export vCard files, upload photos, search/filter/sort lists, perform bulk actions, and use HTMX-enhanced server-rendered interfaces.

The project also needs to demonstrate secure ownership boundaries. Contacts, groups, tags, photos, selection state, import-error reports, and bulk operations must be scoped to the logged-in user. A user should not be able to infer or attach another user's contacts through direct URLs, many-to-many relationships, import flows, admin pages, or HTMX actions.

The decision was to build a Django 5 monolith with Django auth, server-rendered templates, HTMX list/modal updates, ownership-aware model managers, hand-rolled phone/vCard utilities, streaming CSV import/export, soft archive behavior, and PostgreSQL/WhiteNoise production settings.

---

## Decisions

### Decision 1 — Authenticated per-user ownership over session-only storage

**Chosen:** Use Django auth and store `owner` on contacts, groups, and tags.

**Rejected:** Session-scoped contacts or a shared global address book.

**Reason:** Address books are personal data. Per-user ownership is the correct boundary. Unlike earlier session-scoped learner projects, this app needs login, logout, signup, password reset, and durable ownership. The ownership rule is centralized in `OwnedManager.for_user()` and `get_for_user_or_404()` so views ask the model layer for scoped data.

---

### Decision 2 — Ownership-aware manager (404 for missing and unauthorized)

**Chosen:** `get_for_user_or_404()` uses `get_object_or_404(self.for_user(user), **kwargs)` — returns the record when owned, raises `Http404` for both missing rows and rows owned by another user.

**Rejected:** Open-coding `owner=request.user` filters in every view, or returning 403 for cross-user access (leaks primary-key existence).

**Reason:** A central manager reduces duplicated security logic. Returning 404 for unauthorized access avoids leaking whether a given ID exists. See [docs/SECURITY.md](docs/SECURITY.md).

---

### Decision 3 — Scalar primary contact fields plus related phone/email rows

**Chosen:** `Contact` keeps primary scalar `email` and `phone` fields, while related `Phone` and `Email` rows support export and future multi-contact-method UI.

**Rejected:** Full formset-first multi-phone/multi-email editing in v1.

**Reason:** Primary scalar fields keep the core form simple and CSV import/export straightforward. Related rows still exist for vCard generation and future expansion. `ContactForm.sync_primary_records()` keeps the primary scalar fields and related rows aligned.

---

### Decision 4 — Soft archive over immediate delete

**Chosen:** Normal delete/archive actions set `is_archived=True`. Permanent delete is available only from archive/bulk-delete paths.

**Rejected:** Hard delete as the default contact deletion behavior.

**Reason:** Address book data is easy to delete accidentally. Archiving gives recovery, supports an archive view, and preserves user trust. Permanent deletion still exists for intentional cleanup.

---

### Decision 5 — Groups and tags as owned many-to-many organization tools

**Chosen:** `Group` and `Tag` are owner-scoped models with many-to-many relations to `Contact`. Signals prevent cross-owner contacts/groups/tags from being linked.

**Rejected:** Unowned global groups/tags or comma-separated labels on contacts.

**Reason:** Organization metadata is also private user data. Per-user groups/tags avoid leaking one user's taxonomy to another and make list filters predictable. Signals protect many-to-many additions even outside normal forms.

---

### Decision 6 — HTMX with server-rendered templates over SPA

**Chosen:** Django templates render full pages and HTMX partials for contact lists, modal forms, selection, and bulk updates.

**Rejected:** React/Vue SPA or a JSON API-first architecture.

**Reason:** The app is form- and table-heavy. Django forms, template partials, messages, redirects, and permission checks already fit the workload. HTMX gives partial updates while keeping server-rendered HTML as the single UI source of truth.

---

### Decision 7 — Streaming CSV import/export

**Chosen:** CSV export uses generator rows; CSV import streams decoded input, validates row by row, imports valid rows, and stores per-row errors for a downloadable error report.

**Rejected:** Loading the entire file into memory or rejecting the whole file on the first bad row.

**Reason:** CSV files can be large enough to merit streaming discipline. Partial success is more useful for users than all-or-nothing import. Row-level error reports make correction practical.

---

### Decision 8 — Hand-rolled phone normalization and vCard subset

**Chosen:** Implement E.164/US 10-digit phone normalization and a vCard 3.0 subset in project code.

**Rejected:** Adding external phone-number or vCard libraries.

**Reason:** The scope is intentionally small and dependency-light. The project needs predictable behavior for common US/E.164 inputs and basic vCard interoperability, not complete global telecom parsing or every vCard feature.

---

### Decision 9 — Private photo delivery behind views

**Chosen:** Store uploaded photos through Django file storage but serve them through `/contacts/<id>/photo/` after login and ownership checks.

**Rejected:** Public `/media/` URLs.

**Reason:** Contact photos are private address-book data. Serving through a view preserves ownership enforcement. The known production trade-off is that local-disk media on ephemeral hosting can be lost without external object storage.

---

### Decision 10 — Production fail-fast configuration

**Chosen:** Production settings require `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS`; production uses PostgreSQL configuration, WhiteNoise, secure cookies, HTTPS redirect, configurable HSTS (subdomains/preload default off), and static manifest storage. Pinned deps in `requirements-lock.txt`; release step runs migrate + collectstatic before Gunicorn (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

**Rejected:** Production boot with development defaults.

**Reason:** A contact-management app stores personal data. Unsafe production defaults should fail immediately instead of silently deploying insecurely.

---

## Consequences

**Positive:**
- Users have durable private address books.
- Ownership is enforced through managers, signals, admin scoping, and views.
- Contacts can be archived/restored instead of immediately destroyed.
- CSV import/export and vCard export make data portable.
- HTMX improves list and modal workflows without a frontend framework.
- Private photo serving avoids public media links.
- Tests cover ownership, validators, forms, imports, exports, HTMX, admin, and production settings.

**Negative / Trade-offs:**
- Authentication adds more scope than session-only apps.
- CSV round trip covers primary scalar fields only, not groups/tags/secondary phone/email rows.
- Hand-rolled vCard is a useful subset, not a complete standard implementation.
- Uploaded photos need external storage for durable production hosting.
- HTMX partials require careful branching in views.
- Tailwind and HTMX CDN usage is convenient but not ideal for strict production CSP/offline use.

---

## Alternatives Not Explored

- Full RBAC or organization-shared address books.
- Complete vCard/contact-card standards implementation.
- Client-side SPA with REST API.
- Multi-phone/multi-email formsets in the main UI.
- External object storage for photos in v1.
- Real-time collaboration or contact sharing.

---

*Constitution reference: Article 1 (architectural thinking), Article 3.4 (larger project classification), Article 4 (engineering quality), Article 6 (behavior verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — Address Book Portal
**Contact Management Group | Document 2 of 5**

---

## Overview

Address Book Portal is a Django 5 application for authenticated personal contact management. It includes dashboard metrics, contact CRUD, favorites, archive/restore, private photo serving, group/tag organization, search/filter/sort, bulk actions, CSV import/export, vCard export, signup/login/password reset integration, HTMX partials, and production settings for PostgreSQL and WhiteNoise.

**Project package:** `config`  
**Primary app:** `contacts`  
**Local settings:** `config.settings.dev`  
**Production settings:** `config.settings.prod`  
**Primary local database:** SQLite  
**Production database:** PostgreSQL via `DATABASE_URL` or explicit PostgreSQL env vars  
**Frontend:** Django templates, HTMX, Tailwind CDN  
**Ownership model:** Django authenticated user

---

## Data Flow

### Contact list request

```text
GET /contacts/
     │
     ▼
@login_required contact_list()
     │
     ▼
list_context(request, mode="active")
     │
     ├── base_contact_queryset()
     │     ├── Contact.objects.for_user(request.user)
     │     ├── active/favorites/archive mode
     │     ├── search(q)
     │     ├── group/tag filters after ownership check
     │     └── sort/direction
     │
     ├── Paginator(page size 25)
     ├── prune_selected_ids()
     ├── user groups/tags
     └── BulkActionForm(user, list_mode)
     │
     ▼
Full template or HTMX _contact_rows partial
```

---

### Contact create/edit flow

```text
POST /contacts/new/ or /contacts/<id>/edit/
     │
     ▼
ContactForm(request.POST, request.FILES)
     │
     ├── normalize primary phone
     ├── validate required first name
     ├── validate photo through ImageField/Pillow path
     └── form.is_valid()
     │
     ▼
contact.owner = request.user
contact.save(resize_photo=True if needed)
form.sync_primary_records(contact)
     │
     ├── update/create mobile row (is_scalar_sync=True)
     ├── update/create other email row (is_scalar_sync=True)
     └── leave unrelated Phone/Email rows untouched
     │
     ▼
Redirect or HTMX row refresh
```

---

### CSV import flow

```text
POST /import/
     │
     ▼
CSVImportForm
     ├── extension .csv
     └── max size 5 MB
     │
     ▼
stream_import_contacts(owner, uploaded_file)
     │
     ├── decode UTF-8-SIG chunks
     ├── csv.DictReader
     ├── build_field_map(header aliases)
     ├── per-row validation
     ├── Contact.full_clean()
     ├── transaction.atomic()
     ├── create Contact
     ├── create primary Phone/Email records
     └── collect RowError entries
     │
     ▼
messages + optional session-backed error report
```

---

### Bulk action flow

```text
POST /bulk/
     │
     ▼
prune_selected_ids()
BulkActionForm(user, list_mode)
selected_contacts_for_mode()
     │
     ├── archive contacts
     ├── delete permanently from archive
     ├── add group
     ├── add tag
     └── remove tag
     │
     ▼
clear selected IDs when appropriate
redirect or HTMX rows_response()
```

---

### Private photo flow

```text
GET /contacts/<id>/photo/
     │
     ▼
Contact.objects.get_for_user_or_404(request.user, pk=id)
     │
     ├── if no photo: 404
     ├── guess content type
     └── FileResponse(contact.photo.open("rb"))
```

---

## Module-Level Structure

```text
Address-Book-Portal/
  manage.py
  config/
    settings/
      base.py
      dev.py
      prod.py
    database.py
    urls.py
    wsgi.py
    asgi.py
    tests/
  contacts/
    admin.py
    apps.py
    csv_utils.py
    exporters.py
    forms.py
    importers.py
    models.py
    session_selection.py
    signals.py
    signup_urls.py
    urls.py
    utils.py
    validators.py
    views.py
    templatetags/
    migrations/
    tests/
  templates/
    base.html
    registration/
    contacts/
      partials/
  static/
  fixtures/
    seed_data.json
  docs/
    REPORT.md
    TESTING.md
    TRACEABILITY.md
    adr/
  pyproject.toml
  requirements.txt
  railway.json
```

---

## Module Dependency Graph

```text
config.urls
  ├── django admin
  ├── contacts.signup_urls
  ├── django.contrib.auth.urls
  └── contacts.urls

contacts.urls
  └── contacts.views

contacts.views
  ├── Contact / Group / Tag
  ├── ContactForm / GroupForm / TagForm / BulkActionForm / CSVImportForm
  ├── exporters.csv_contact_rows / contact_to_vcard / vcards_for_contacts
  ├── importers.stream_import_contacts / error_report_rows
  ├── session_selection helpers
  └── utils.upcoming_birthdays

contacts.models
  ├── validators.normalize_phone_number / validate_phone_number / validate_hex_color
  ├── OwnedQuerySet / OwnedManager
  ├── Contact / Phone / Email / Group / Tag
  └── photo resize through Pillow when requested

contacts.forms
  ├── UserCreationForm
  ├── Contact / Phone / Email / Group / Tag
  └── validators

contacts.signals
  ├── m2m_changed for Group.contacts / Tag.contacts
  ├── user_logged_in
  └── user_logged_out

contacts.exporters
  ├── csv
  ├── base64
  ├── mimetypes
  ├── CsvEcho
  └── Phone / Email

contacts.importers
  ├── csv
  ├── codecs
  ├── transaction.atomic
  ├── Contact / Phone / Email
  └── RowError / ImportResult

config.settings.prod
  ├── config.database.postgres_from_url
  ├── WhiteNoise middleware/storage
  └── secure production settings
```

---

## Core Data Structures

### `OwnedQuerySet`

Methods:
- `for_user(user)`
- `active()`
- `archived()`
- `favorites()`
- `search(query)`

Purpose: centralize ownership and common contact filtering.

---

### `OwnedManager`

Important method:

```python
get_for_user_or_404(user, **kwargs)
```

Behavior:
- returns object if owned by user
- raises `Http404` if object is missing or belongs to another user

---

### `Contact`

Fields:
- `uuid` (stable vCard UID)
- `owner`
- `first_name`
- `last_name`
- `email`
- `phone`
- `company`
- `job_title`
- `notes`
- `birthday`
- `photo`
- `is_favorite`
- `is_archived`
- timestamps

Computed properties:
- `display_name`
- `initials`
- `photo_url`
- `display_phone`
- `display_email`

Methods:
- `get_absolute_url()`
- `clean()`
- `save(resize_photo=False)`
- `_resize_photo()`
- `soft_delete()`
- `restore()`

---

### `Phone`

Fields:
- `contact`
- `number`
- `label`

Labels:
- mobile
- work
- home

Behavior:
- normalizes/validates number in `clean()` and `save()`

---

### `Email`

Fields:
- `contact`
- `address`
- `label`

Labels:
- work
- home
- other

---

### `Group`

Fields:
- `owner`
- `name`
- `contacts`

Rule:
- case-insensitive unique name per owner

---

### `Tag`

Fields:
- `owner`
- `name`
- `color`
- `contacts`

Rules:
- case-insensitive unique name per owner
- color must be hex format like `#2563eb`

---

### `RowError`

```python
@dataclass
class RowError:
    row_number: int
    data: dict
    errors: dict
```

Stores import row errors for user feedback and CSV error-report export.

---

### `ImportResult`

```python
@dataclass
class ImportResult:
    imported_count: int = 0
    errors: list[RowError] = field(default_factory=list)
```

Computed property:
- `failed_count`

---

## Function and Class Reference

### `contact_photo_path(instance, filename)`

Creates a private per-user photo path:

```text
contacts/user_<owner_id>/photos/<uuid><suffix>
```

---

### `normalize_phone_number(value)`

Accepts:
- 10-digit US numbers
- 11-digit US numbers starting with 1
- E.164 numbers with one leading plus
- punctuation/spaces used for formatting

Rejects:
- letters
- invalid plus usage
- unsupported lengths
- invalid characters

---

### `validate_hex_color(value)`

Requires:

```text
#[0-9A-Fa-f]{6}
```

---

### `ContactForm.sync_primary_records(contact)`

Keeps scalar primary `phone`/`email` synchronized with related records marked `is_scalar_sync=True`:
- updates or creates the scalar-sync mobile phone from `contact.phone`
- updates or creates the scalar-sync other email from `contact.email`
- does not delete unrelated Phone/Email rows created in admin or shell

---

### `BulkActionForm`

Adapts available actions by list mode:
- active/favorites modes allow archive, add group, add tag, remove tag
- archive mode allows permanent delete, add group, add tag, remove tag

Requires a group/tag selection for corresponding actions.

---

### `stream_import_contacts(owner, uploaded_file)`

Streams CSV input, maps header aliases, validates rows, creates contacts and primary related records, and returns `ImportResult`.

Failure handling:
- missing header row
- duplicate mapped columns
- too many columns
- missing first name
- invalid birthday
- invalid phone
- non-UTF-8 CSV

---

### `csv_contact_rows(queryset)`

Streams CSV rows for primary scalar contact fields:
- first name
- last name
- email
- phone
- company
- job title
- birthday
- notes

---

### `contact_to_vcard(contact)`

Builds a vCard 3.0 string with:
- name
- full name
- organization
- title
- emails
- phones
- birthday
- notes
- optional base64 photo line

Includes escaping and UTF-8 line folding.

---

### `upcoming_birthdays(contacts, today=None, within_days=30)`

Returns upcoming birthdays sorted by date. Leap-day birthdays are handled by falling back to February 28 in non-leap years.

---

### `postgres_from_url(database_url)`

Parses a PostgreSQL URL into a Django database dictionary, including optional `sslmode` query parameter.

---

## View Reference

### `signup`

Creates a user, logs them in, and redirects to dashboard.

---

### `dashboard`

Shows:
- total contacts
- total groups
- total tags
- recent additions
- upcoming birthdays
- recently updated contacts

---

### `contact_list(mode='active')`

Renders active, favorites, or archive list mode. Returns full page or HTMX rows partial.

Supports:
- search query
- group filter
- tag filter
- sort and direction
- pagination
- bulk selection state

---

### `organization`

Creates and displays groups/tags. Handles duplicate names through form validation and database integrity handling.

---

### `contact_detail`

Shows a single owned contact.

---

### `contact_photo`

Streams contact photo after login and ownership check.

---

### `contact_create` / `contact_update`

Create/update contacts with full form validation. HTMX requests receive modal partials or refreshed rows.

---

### `contact_delete` / `contact_restore`

Archive and restore contacts.

---

### `contact_toggle_favorite`

Toggles favorite state and updates the current list mode.

---

### `selection_toggle`, `selection_clear`, `selection_page`

Maintain selected contact IDs in session while pruning IDs that no longer belong to the user.

---

### `bulk_action`

Applies archive, permanent delete, group add, tag add, and tag removal to selected contacts in the current mode.

---

### `csv_import`

Validates upload and streams imported contacts. Stores import errors in the session for later error-report download.

---

### `csv_error_report`

Streams row-level import errors as CSV, then clears the saved error state.

---

### `csv_export`

Streams contacts in CSV for the current filtered mode.

---

### `vcard_export_one` / `vcard_export_bulk`

Exports one contact or a filtered set as vCard.

---

## State Management

### Database state

- Django users and auth/session rows
- contacts
- phones
- emails
- groups
- tags
- many-to-many join rows

### Session state

- selected contact IDs
- selected-contact owner binding
- last CSV import errors
- import-error owner binding

### File state

- uploaded photos in `MEDIA_ROOT`
- static files collected to `STATIC_ROOT`
- logs written to `logs/address_book.log` when directory creation succeeds

---

## Error Handling Strategy

- Login required for all address-book pages except signup/auth routes.
- Ownership manager returns **404** for missing and cross-owner rows (no PK leak).
- Many-to-many signals block cross-owner contact/group/tag links.
- Import row errors are collected without aborting the whole file.
- Import error report returns 404 if no report exists.
- Missing contact photo returns 404.
- Duplicate group/tag names are handled by form validation and IntegrityError fallback.
- Production settings raise `ImproperlyConfigured` for missing required environment variables.

---

## External Dependencies

| Dependency | Purpose |
|---|---|
| Django | Web framework, auth, ORM, forms, templates |
| Pillow | Contact photo/image handling |
| psycopg[binary] | PostgreSQL support |
| python-dotenv | Local `.env` loading |
| gunicorn | Production WSGI server |
| whitenoise | Production static files |
| coverage | Coverage measurement |
| pytest / pytest-django | Test execution |

Frontend:
- HTMX
- Tailwind CSS CDN

---

## Concurrency Model

The app is synchronous Django. CSV import uses per-row `transaction.atomic()` for contact plus related primary phone/email creation. Exports stream generator output. There are no async views, background workers, websockets, or task queues.

---

## Known Limitations

- CSV round trip covers primary scalar fields only.
- Main contact form edits one primary phone and email only.
- vCard generation is a hand-rolled subset.
- Uploaded photos use local disk unless external storage is added.
- Tailwind/HTMX CDN dependency remains a production hardening gap.
- No shared address books or RBAC.
- Password reset needs production email backend configuration.

---

## Design Patterns Used

- **Django MVT**
- **Ownership-aware manager**
- **Server-rendered HTMX partials**
- **Soft archive**
- **Streaming import/export**
- **Session-backed bulk selection**
- **Signal-based cross-owner guard**
- **Fail-fast production settings**
- **Private media through view authorization**

---

## Verification Summary

The documentation and test files report **377 passing tests** and **95.0%** measured application coverage (`contacts` + `config`, omitting `prod.py`; CI floor 90%). See [docs/TESTING.md](docs/TESTING.md). Tests cover ownership, validators, import/export, HTMX flows, select-all UI markup, photo validation, dashboard metrics, forms, signals, admin scoping, production settings (subprocess), database URL parsing, birthday math, session selection, bulk actions, and template tag helpers.

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — Address Book Portal
**Contact Management Group | Document 3 of 5**

---

## Public Web Interface

| Method | Path | View | Success Status | Description |
|---|---|---|---:|---|
| `GET` | `/` | `dashboard` | 200 | Dashboard for logged-in user |
| `GET` | `/contacts/` | `contact_list` | 200 | Active contacts |
| `GET` | `/contacts/favorites/` | `contact_list(mode=favorites)` | 200 | Favorite contacts |
| `GET` | `/contacts/archive/` | `contact_list(mode=archive)` | 200 | Archived contacts |
| `GET`/`POST` | `/contacts/new/` | `contact_create` | 200/302 | Create contact |
| `GET` | `/contacts/<pk>/` | `contact_detail` | 200 | Contact detail |
| `GET` | `/contacts/<pk>/photo/` | `contact_photo` | 200/404 | Private photo stream |
| `GET`/`POST` | `/contacts/<pk>/edit/` | `contact_update` | 200/302 | Edit contact |
| `POST` | `/contacts/<pk>/delete/` | `contact_delete` | 302/204 | Archive contact |
| `POST` | `/contacts/<pk>/restore/` | `contact_restore` | 302/204 | Restore contact |
| `POST` | `/contacts/<pk>/favorite/` | `contact_toggle_favorite` | 302/204 | Toggle favorite |
| `GET` | `/contacts/<pk>/vcard/` | `vcard_export_one` | 200 | Single vCard export |
| `GET`/`POST` | `/organization/` | `organization` | 200/302 | Groups and tags |
| `POST` | `/organization/groups/<pk>/delete/` | `group_delete` | 302 | Delete group |
| `POST` | `/organization/tags/<pk>/delete/` | `tag_delete` | 302 | Delete tag |
| `POST` | `/selection/toggle/` | `selection_toggle` | 200 | Select/unselect contact |
| `POST` | `/selection/clear/` | `selection_clear` | 200/302 | Clear selection |
| `POST` | `/selection/page/` | `selection_page` | 200 | Select/unselect page |
| `POST` | `/bulk/` | `bulk_action` | 200/302 | Bulk archive/delete/group/tag |
| `GET`/`POST` | `/import/` | `csv_import` | 200 | CSV import |
| `GET` | `/import/errors.csv` | `csv_error_report` | 200/404 | Import error report |
| `GET` | `/export/csv/` | `csv_export` | 200 | CSV export |
| `GET` | `/export/vcard/` | `vcard_export_bulk` | 200 | Bulk vCard export |
| `GET`/`POST` | `/accounts/signup/` | `signup` | 200/302 | Registration |
| `GET`/`POST` | `/accounts/login/` | Django auth | 200/302 | Login |
| `GET`/`POST` | `/accounts/password_reset/` | Django auth | 200/302 | Password reset |
| any | `/admin/` | Django admin | varies | Admin |

All contact-management routes require authentication except signup/auth pages.

---

## Invocation Syntax

### Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata seed_data
python manage.py runserver
```

Seed user:

```text
demo / demo-password
```

---

### Production-only install

```powershell
pip install -r requirements.txt
```

---

### Useful commands

```powershell
python manage.py test
pytest
coverage run manage.py test
coverage report
python manage.py createsuperuser
python manage.py collectstatic
```

---

## Form Input Contract

### Signup

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | Yes | Django username |
| `email` | email | Yes | Must be unique case-insensitively |
| `password1` | password | Yes | Django password validation |
| `password2` | password | Yes | Must match |

---

### Contact

| Field | Type | Required | Notes |
|---|---|---|---|
| `first_name` | string | Yes | max 80 |
| `last_name` | string | No | max 80 |
| `email` | email | No | primary email |
| `phone` | string | No | normalized to E.164-like format |
| `company` | string | No | max 120 |
| `job_title` | string | No | max 120 |
| `birthday` | date | No | HTML date input |
| `photo` | file | No | image upload |
| `is_favorite` | boolean | No | favorite flag |
| `notes` | text | No | textarea |

---

### Group

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | case-insensitive unique per user |

---

### Tag

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | case-insensitive unique per user |
| `color` | string | Yes | hex color, e.g. `#2563eb` |

---

### CSV import

| Field | Type | Required | Rules |
|---|---|---|---|
| `file` | file | Yes | `.csv`, max 5 MB, UTF-8 |

Accepted canonical columns:
- first_name
- last_name
- email
- phone
- company
- job_title
- birthday
- notes

Header aliases include common names like `First Name`, `given name`, `email address`, `phone number`, `organization`, `role`, and `date of birth`.

---

### Bulk action

| Field | Type | Required | Notes |
|---|---|---|---|
| `action` | choice | Yes | archive/delete/add_group/add_tag/remove_tag depending on mode |
| `group` | model choice | Required for add_group | user-owned groups only |
| `tag` | model choice | Required for add_tag/remove_tag | user-owned tags only |

---

## Query Parameter Contract

### Contact list

```text
GET /contacts/?q=<query>&group=<id>&tag=<id>&sort=<sort>&dir=<dir>&page=<page>
```

| Parameter | Accepted Values |
|---|---|
| `q` | text search over names, email, phone, company, related phones/emails |
| `group` | user-owned group ID |
| `tag` | user-owned tag ID |
| `sort` | `name`, `company`, `created`, `updated` |
| `dir` | `asc`, `desc` |
| `page` | paginator page |

---

### Export

```text
GET /export/csv/?mode=active|favorites|archive
GET /export/vcard/?mode=active|favorites|archive
```

Uses current filters supported by `base_contact_queryset`.

---

## HTMX Contract

HTMX requests use:

```text
HX-Request: true
```

Possible response behaviors:
- return `_contact_rows.html`
- return `_contact_form.html` into modal root
- set `HX-Retarget: #modal-root` on invalid modal form POST
- set `HX-Reswap: innerHTML`
- set `HX-Redirect` through 204 response for full navigation when appropriate

---

## Output Contract

### CSV export

Content type:

```text
text/csv
```

Filename:

```text
contacts.csv
```

Columns:
- First Name
- Last Name
- Email
- Phone
- Company
- Job Title
- Birthday
- Notes

---

### Import error report

Content type:

```text
text/csv
```

Filename:

```text
address-book-import-errors.csv
```

Columns:
- Row
- Field
- Error

---

### vCard export

Content type:

```text
text/vcard
```

Single filename:

```text
contact-<pk>.vcf
```

Bulk filename:

```text
contacts.vcf
```

---

### Contact photo

Returns `FileResponse` with guessed content type or `application/octet-stream` fallback.

---

## Environment Variables

| Variable | Required | Environment | Description |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes in production | all | Django secret key |
| `DJANGO_DEBUG` | No | dev/prod | Boolean debug flag |
| `DJANGO_ALLOWED_HOSTS` | Yes in production | all | comma-separated hosts |
| `DJANGO_TIME_ZONE` | No | all | default `America/Los_Angeles` |
| `DATABASE_URL` | Production recommended | prod | PostgreSQL URL |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes in production | prod | HTTPS trusted origins |
| `DJANGO_EMAIL_BACKEND` | No | all | email backend override |
| `DJANGO_DEFAULT_FROM_EMAIL` | No | all | password reset sender |
| `DJANGO_LOG_LEVEL` | No | all | root logger level |

---

## Configuration Files

### `.env`

Loaded by `python-dotenv` when available.

---

### `pyproject.toml`

Defines:
- package metadata
- Python `>=3.12`
- runtime dependencies
- optional dev dependencies
- pytest settings
- coverage settings

---

### `requirements.txt`

Production dependencies:
- Django
- Pillow
- psycopg
- python-dotenv
- gunicorn
- whitenoise

---

### `railway.json`

Start command:

```bash
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

---

## Side Effects

| Operation | Side Effect |
|---|---|
| Signup | Creates user and logs them in |
| Contact create/update | Writes contact and syncs primary Phone/Email rows |
| Photo upload | Stores file under per-user media path; may resize via Pillow |
| Archive | Sets `is_archived=True` |
| Restore | Sets `is_archived=False` |
| Bulk delete | Permanently deletes selected archived contacts |
| Selection | Stores selected IDs in session |
| Import | Creates valid contacts; stores row errors in session |
| Error report download | Streams error CSV; session errors persist until next import |
| CSV/vCard export | Streams generated file response (Primary CSV = scalar fields only) |
| Login/logout | Binds or clears session selection/import-error state |
| Production deploy | Release: migrate + collectstatic; web: Gunicorn only |

---

## Usage Examples

### Import contacts

```text
GET /import/
POST /import/
```

CSV example:

```csv
First Name,Last Name,Email,Phone,Company
Ada,Lovelace,ada@example.com,415-555-2671,Analytical Engines
```

---

### Export active contacts

```text
/export/csv/?mode=active
/export/vcard/?mode=active
```

---

### Filter contacts by group and sort by updated descending

```text
/contacts/?group=3&sort=updated&dir=desc
```

---

### Download one vCard

```text
/contacts/<pk>/vcard/
```

---

### Private photo URL

```text
/contacts/<pk>/photo/
```

---

## Public Python Interfaces

Important internal interfaces:
- `OwnedManager.get_for_user_or_404`
- `OwnedQuerySet.for_user`
- `Contact.soft_delete`
- `Contact.restore`
- `ContactForm.sync_primary_records`
- `stream_import_contacts`
- `csv_contact_rows`
- `contact_to_vcard`
- `vcards_for_contacts`
- `normalize_phone_number`
- `upcoming_birthdays`
- `postgres_from_url`

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — Address Book Portal
**Contact Management Group | Document 4 of 5**

---

## Requirements

### Local development

- Python 3.12+
- pip and virtual environment support
- SQLite
- Pillow-supported image stack
- Browser with JavaScript for HTMX-enhanced behavior

### Production

- PostgreSQL
- Gunicorn
- WhiteNoise
- secure secret key
- allowed hosts
- CSRF trusted origins
- SMTP/email backend for password reset
- external media storage recommended for durable uploaded photos

---

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata seed_data
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Seed login:

```text
demo / demo-password
```

---

## Production Setup

Set:

```text
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<strong-secret>
DATABASE_URL=<postgres-url>
DJANGO_ALLOWED_HOSTS=<hostnames>
DJANGO_CSRF_TRUSTED_ORIGINS=<https-origins>
```

Run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Railway can use the included `railway.json` start command.

---

## Running the App

```powershell
python manage.py runserver
```

Expected:
- unauthenticated users redirect to login for private pages
- signup available at `/accounts/signup/`
- dashboard visible after login
- contact list available at `/contacts/`

---

## Running Tests

```bash
pytest -q
coverage run -m pytest -q && coverage report --fail-under=90
```

Reproducible deps: `pip install -r requirements-lock.txt` or `pip install -e ".[dev]"`.

Expected (see README “Last verified”):
- **377** passing tests
- **95.0%** measured application coverage (`prod.py` omitted)
- CI coverage floor **90%**

---

## Standard Operating Procedures

### Create contact

1. Login.
2. Open `/contacts/`.
3. Click/create new contact.
4. Enter first name and optional details.
5. Save.
6. Confirm the contact appears in the active list.

---

### Update contact

1. Open contact detail or edit modal.
2. Edit fields.
3. Save.
4. Confirm primary related phone/email sync still reflects scalar fields.

---

### Archive and restore

1. Archive from list or detail.
2. Open `/contacts/archive/`.
3. Restore contact.
4. Confirm it returns to active list.

---

### Bulk actions

1. Select contacts from a list page.
2. Choose action:
   - archive
   - delete permanently in archive
   - add group
   - add tag
   - remove tag
3. Submit.
4. Confirm selected IDs are cleared or pruned as expected.

---

### Import contacts

1. Open `/import/`.
2. Upload CSV under 5 MB.
3. Review success/error messages.
4. Download `/import/errors.csv` if failures exist.

---

### Export contacts

```text
/export/csv/?mode=active
/export/vcard/?mode=active
```

For one contact:

```text
/contacts/<pk>/vcard/
```

---

### Manage organization

1. Open `/organization/`.
2. Create groups/tags.
3. Apply via bulk actions.
4. Delete unused groups/tags when needed.

---

## Health Checks

### Login page

```text
GET /accounts/login/
```

Healthy:
- HTTP 200
- login form visible

---

### Dashboard

```text
GET /
```

Healthy after login:
- HTTP 200
- contact/group/tag counts visible

---

### Contact list

```text
GET /contacts/
```

Healthy:
- HTTP 200
- active contacts list visible
- filters/sort controls visible

---

### HTMX rows

```text
GET /contacts/
HX-Request: true
```

Healthy:
- returns contact rows partial

---

### Import/export

```text
GET /import/
GET /export/csv/
GET /export/vcard/
```

Healthy:
- import page renders
- exports stream attachment responses

---

### Production static

```bash
python manage.py collectstatic --noinput
```

Healthy:
- static files collect without manifest errors

---

## Expected Output Samples

### CSV export header

```csv
First Name,Last Name,Email,Phone,Company,Job Title,Birthday,Notes
```

---

### Import error report header

```csv
Row,Field,Error
```

---

### vCard output

```text
BEGIN:VCARD
VERSION:3.0
N:Last;First;;;
FN:First Last
END:VCARD
```

---

## Known Failure Modes

### Production refuses to start

**Trigger:** Missing `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, or `DJANGO_CSRF_TRUSTED_ORIGINS`.

**Resolution:** Set required production environment variables.

---

### Contact photo returns 404

**Trigger:** Contact has no photo or current user does not own the contact.

**Resolution:** Upload a photo for an owned contact.

---

### CSV import fails rows

**Common causes:**
- missing first name
- invalid phone
- invalid birthday format
- too many columns
- duplicate header aliases
- non-UTF-8 encoding

**Resolution:** Download error report, fix CSV, re-upload.

---

### CSV upload rejected

**Trigger:** File is not `.csv` or is over 5 MB.

**Resolution:** Upload smaller CSV file with `.csv` extension.

---

### Cross-user contact access returns 404

**Trigger:** URL points to an existing record owned by another user (same response as a missing ID).

**Resolution:** Use only records owned by current account.

---

### Group/tag duplicate errors

**Trigger:** Same group/tag name for the same owner, case-insensitively.

**Resolution:** Use a unique name.

---

### Uploaded photos disappear after deployment

**Trigger:** Ephemeral local media storage on hosting platform.

**Resolution:** Add external object storage and update media storage backend.

---

## Troubleshooting Decision Tree

```text
App does not start
  ├── Missing dependencies?
  │     └── pip install -e ".[dev]" or pip install -r requirements.txt
  ├── Database unmigrated?
  │     └── python manage.py migrate
  ├── Production env missing?
  │     └── set secret key, hosts, CSRF origins, database
  └── Static manifest issue?
        └── run collectstatic

Contact not visible
  ├── Wrong user?
  │     └── login as owner
  ├── Archived?
  │     └── check /contacts/archive/
  ├── Filter hiding it?
  │     └── clear q/group/tag/sort filters
  └── Import failed?
        └── download error report

Bulk action not working
  ├── No selected contacts?
  │     └── select rows first
  ├── Selection bound to another user?
  │     └── logout/login clears or rebinds state
  ├── Missing group/tag selection?
  │     └── choose required object
  └── Contact no longer in current mode?
        └── prune selected IDs by reloading list
```

---

## Dependency Failure Handling

### Python packages

```powershell
pip install -e ".[dev]"
```

Production:

```powershell
pip install -r requirements.txt
```

---

### PostgreSQL

Check:
- `DATABASE_URL`
- host/user/password/database
- optional `sslmode`
- psycopg installation

---

### Email backend

Configure:
- `DJANGO_EMAIL_BACKEND`
- `DJANGO_DEFAULT_FROM_EMAIL`
- provider-specific SMTP settings if needed

---

### Static files

```powershell
python manage.py collectstatic --noinput
```

---

## Recovery Procedures

### Recover from bad local DB

```powershell
Remove-Item db.sqlite3
python manage.py migrate
python manage.py loaddata seed_data
```

---

### Recover archived contact

1. Open `/contacts/archive/`.
2. Click Restore.
3. Confirm contact appears in active list.

---

### Recover import errors

1. Download `/import/errors.csv` after failed import.
2. Fix rows in source CSV.
3. Re-upload.

---

### Recover lost uploaded photos

If media disappeared on ephemeral hosting, restore from backups or migrate to external storage. The repo design does not include durable external media storage in v1.

---

## Logging Reference

The app logs to:
- console
- `logs/address_book.log` when log directory can be created

File handler:
- rotating log
- max size 1 MB
- 3 backups

Configure level:

```text
DJANGO_LOG_LEVEL=INFO
```

---

## Maintenance Notes

- Keep all object lookups ownership-scoped.
- Keep cross-owner M2M signal checks when changing group/tag behavior.
- Revisit media storage before public production deployment.
- Expand CSV import/export only if groups/tags/secondary phone/email round-trip is intentionally designed.
- Add golden vCard fixtures before claiming broad client compatibility.
- Configure real email backend for password reset in production.
- Re-run tests after changing import/export, ownership, admin, or HTMX list behavior.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — Address Book Portal
**Contact Management Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because an address book is fundamentally about private ownership. A contact manager that allows another user to see, attach, export, or download someone else's records would fail at the core use case. That pushed ownership into the model manager, not just into view filters.

Django was the right framework because the app needs exactly what Django is good at: auth, forms, ORM relationships, admin, password reset, templates, file uploads, streaming responses, and production settings. HTMX adds a smoother UI while preserving server-rendered forms and permission checks.

The scalar-plus-related contact method design was a practical compromise. Primary phone/email fields keep the form simple and CSV-friendly, while related `Phone` and `Email` rows support vCard and future multi-method UI.

---

## What Was Intentionally Omitted

**Shared address books:** Omitted to avoid RBAC and organization membership complexity.

**Multi-phone/multi-email formsets:** Related models exist, but the main UI edits primary fields only.

**Full vCard standard coverage:** The exporter implements a practical vCard 3.0 subset.

**External media storage:** Deferred; local disk works for development but is weak on ephemeral hosting.

**SPA/API frontend:** Server-rendered templates and HTMX are enough for v1.

**CSV round-trip for groups/tags:** CSV intentionally covers primary scalar fields only.

---

## Biggest Weakness

The biggest weakness is media persistence. Contact photos are private and correctly served behind ownership checks, but local disk media is not durable on many modern hosting platforms. A public deployment should add S3-compatible storage or another persistent media backend.

The second weakness is CSV round-trip scope. Import/export handles the primary contact fields, but groups, tags, favorites, archive flags, and secondary phone/email rows are not preserved. That is acceptable for v1 but important to document.

The third weakness is form simplicity. The database supports multiple phones and emails, but the primary UI exposes only one primary phone and email. This keeps the product usable but leaves data-model capability underused.

---

## Scaling Considerations

**If sharing is added:**
- introduce organizations or address books as containers
- add roles/permissions
- replace owner-only queries with membership-aware scopes
- redesign cross-owner group/tag signals

**If contact data grows large:**
- add database indexes for common search/filter fields
- consider full-text search
- make exports asynchronous for very large datasets
- add pagination tuning

**If import/export grows:**
- add mapping preview
- add duplicate detection
- add group/tag/secondary field round-trip
- add golden-file vCard tests

**If production hardens:**
- external media storage
- compiled/self-hosted frontend assets
- stronger CSP
- SMTP provider configuration
- database backups and restore testing

---

## What the Next Refactor Would Be

1. **Add multi-phone/multi-email formsets** — expose the related models directly in the UI.

2. **Move photos to external storage** — make private media durable across deploys.

3. **Expand CSV import/export schema** — include groups, tags, favorite/archive flags, and secondary rows.

4. **Add duplicate detection** — catch likely duplicate contacts on import and creation.

5. **Self-host frontend assets** — replace CDN Tailwind/HTMX with production-ready static assets.

6. **Add vCard golden fixtures** — improve confidence against real-world contact clients.

---

## What This Project Taught

- **Ownership is architecture.** Per-user filtering should not be an afterthought in each view. It belongs in reusable model/query interfaces.

- **Privacy affects media routing.** Serving photos through `/media/` would be simple but wrong for private contacts. The view-based photo route is a better design.

- **Import workflows need partial success.** Users benefit from importing valid rows and receiving a report for bad rows.

- **Simple formats still have edge cases.** CSV headers, UTF-8 BOMs, row length, date formats, phone formats, and vCard line folding all matter.

- **Admin is another security surface.** Non-superuser admin querysets and many-to-many ownership validation matter even when normal views are protected.

- **HTMX works well with Django forms.** Modal and list-row updates can stay server-rendered without building an API client.

- **Tests are protection for privacy.** Ownership, cross-user access, import/export, and admin scoping tests are not extras; they are core product safety checks.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for Address Book Portal.*
