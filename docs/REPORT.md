# Address Book Portal — Project Report

## Abstract

Address Book Portal is a Django 5 web application that gives each authenticated user a private address book. It uses server-rendered templates with HTMX for partial page updates, enforces per-user data ownership at the ORM layer, and implements CSV import/export and hand-rolled vCard generation without extra format libraries.

The project demonstrates full-stack web development: relational modeling, auth, validation, streaming I/O, hypermedia UI patterns, and documented architectural tradeoffs.

## Goals

- Personal contact management with groups, tags, favorites, and soft archive
- Secure multi-user isolation without a complex RBAC system
- CSV and vCard interchange with minimal dependencies
- Responsive UI suitable for desktop and mobile
- Test coverage focused on correctness-critical paths

## Architecture

```
Browser (HTMX + Tailwind CDN)
        ↓ HTTP
Django views (orchestration, HTMX branching)
        ↓
Models / forms / validators / importers / exporters
        ↓
SQLite (dev) or PostgreSQL (prod)
```

**Ownership:** `OwnedManager.for_user()` scopes queries; `get_for_user_or_404()` returns 403 when a row exists but belongs to another user.

**HTMX:** List mutations swap `#contact-table-body`; modals post to create/edit endpoints and either refresh rows or redirect via `HX-Redirect`.

**Import/export:** Generator-based CSV and vCard output; streaming CSV import with per-row validation and partial success.

See [ADR 0001](adr/0001-htmx-over-spa.md), [ADR 0002](adr/0002-hand-rolled-phone-and-vcard.md), [ADR 0003](adr/0003-per-user-ownership-over-rbac.md), and [ADR 0004](adr/0004-scalar-and-related-contact-fields.md).

## Implementation Highlights

| Area | Approach |
|------|----------|
| Phone validation | Hand-rolled E.164 / US 10-digit normalizer |
| vCard | RFC 6350 subset with escaping and line folding |
| Bulk selection | Server-side session set, pruned on load |
| Birthdays | Leap-day safe date math in `contacts/utils.py` |
| Static files | WhiteNoise in production |

## Limitations

1. **Primary-field UI** — Only one phone and email are editable in forms; related models exist for export and future use (ADR 0004).
2. **Favorites vs archive** — Favorited contacts that are archived do not appear in the Favorites view because it lists active contacts only.
3. **Media on Railway** — Uploaded photos use local disk; redeploys on ephemeral hosting can lose files unless external storage is added.
4. **Email in production** — Password reset uses the console backend in development; production needs SMTP configuration.
5. **CDN frontend** — Tailwind and HTMX load from CDNs for simplicity, not offline/air-gapped use.
6. **No shared address books** — Single-tenant per-user ownership by design (ADR 0003).

## Future Work

- Multi-phone / multi-email formsets in the UI
- Optional organization-level sharing or RBAC
- External media storage (S3-compatible)
- Golden-file vCard fixtures for broader client compatibility testing
- Dark mode theme toggle

## Testing

Tests target ownership, validators, import/export, HTMX flows, and edge cases (leap-day birthdays, bulk actions, duplicate group names). Run:

```powershell
python manage.py test
pytest
coverage run manage.py test
coverage report
```

See [TESTING.md](TESTING.md) for the latest measured coverage and scope notes.

## Conclusion

The project meets its academic scope: a complete address book with deliberate design choices, minimal dependencies, and tested critical paths. Documented ADRs and known limitations make the tradeoffs explicit rather than accidental.
