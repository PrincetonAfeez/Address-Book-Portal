# Security Overview

Threat model and security controls for the Address Book Portal academic project.

## Assets

| Asset | Sensitivity | Storage |
|-------|-------------|---------|
| Contact records (PII) | High | PostgreSQL / SQLite |
| Contact photos | High | Private media storage |
| Session selection / import errors | Medium | Django session store |
| User credentials | High | Django `auth_user` (hashed passwords) |

## Actors

| Actor | Trust |
|-------|-------|
| Authenticated owner | Trusted for own data only |
| Another authenticated user | Untrusted — must not read or mutate others' rows |
| Anonymous visitor | Untrusted — auth required for all contact features |
| Admin staff | Trusted within owner-scoped admin; superuser sees all |

## Controls

### Authentication and session

- Django session authentication for browser UI
- `@login_required` on contact views
- Logout clears bulk selection and import-error session keys (`clear_session_on_logout`)

### Authorization (ownership)

- `OwnedManager.for_user()` scopes querysets to `request.user`
- `get_for_user_or_404()` returns **404** for missing and unauthorized rows (no cross-user PK leak)
- M2M signals block linking contacts across owners (`validate_group_contacts`, `validate_tag_contacts`)
- Admin querysets and FK widgets scoped for non-superusers

See [ADR 0003](adr/0003-per-user-ownership-over-rbac.md).

### Media privacy

- Photos served at `/contacts/<id>/photo/` behind login + ownership check
- Responses set `Cache-Control: private, no-store`
- Direct `/media/` URLs are not exposed in production
- Replaced/deleted photos removed from storage via signals

### Input validation

- Hand-rolled phone normalization (`validators.py`)
- Photo upload: size, MIME, and dimension limits in `ContactForm`
- CSV formula injection mitigated with `safe_csv_cell()` on export
- Model `full_clean()` on `Contact.save()` (forms and import path)

### CSV import/export

- **Primary scalar fields only** — not a full backup format; see [ADR 0004](adr/0004-scalar-and-related-contact-fields.md)
- Import errors capped at 500 rows in session (`MAX_IMPORT_ERRORS`)
- Duplicate email/phone rows skipped on re-import
- Import file size limit on upload form

### Transport and deployment

- Production requires `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- CSRF on all mutating forms; HTMX sends token via `htmx:configRequest`
- HSTS subdomains/preload default **off**; enable via env for production domains (see [DEPLOYMENT.md](DEPLOYMENT.md))
- HTMX and Lucide loaded from CDN with Subresource Integrity; Tailwind CDN documented as runtime tradeoff

### Admin

- Staff users see only their own contacts/groups/tags unless superuser
- Related Phone/Email admin FK limited to owned contacts

## Known risks and accepted tradeoffs

| Risk | Mitigation / status |
|------|---------------------|
| CDN supply chain (Tailwind runtime) | Pin HTMX/Lucide with SRI; document vendoring path |
| Session fixation / hijacking | Django defaults; HTTPS required in production |
| CSV not full-fidelity backup | UI labeled “Primary CSV”; docs and import banner |
| Scalar + related phone/email drift | `is_scalar_sync` flag; sync only managed rows |
| No rate limiting on login/import | Out of scope for v1; use platform/WAF in production |
| `QuerySet.update()` bypasses model validation | Documented on `Contact`; portal uses forms/save |

## Verification tests

Cross-user isolation, photo access, CSV safety, and admin scoping are covered in:

- `test_audit_fixes.py`, `test_views.py`, `test_contact_photo.py`
- `test_media_import_fixes.py`, `test_applied_fixes.py`
- `config/tests/test_prod_settings.py` (production env contract)

See [TRACEABILITY.md](TRACEABILITY.md) for the full mapping.
