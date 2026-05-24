# Project Specification Summary

This document summarizes the Address Book Portal requirements for graders and reviewers. The full instructor spec lives in `Address Book Portal.txt` (local/gitignored copy).

## Core requirements

- Django web application with authenticated users and **per-user data ownership**
- Contact CRUD with search, sort, pagination, favorites, and soft archive
- Groups and tags for organization and filtering
- Bulk selection and bulk actions (archive, restore, tag, group, delete)
- CSV import (partial success + error report) and CSV/vCard export
- HTMX-enhanced list UI with modal create/edit
- Hand-rolled phone validation and vCard 3.0 export subset
- Split settings: development (SQLite) and production (PostgreSQL, WhiteNoise)
- Test suite with coverage gate in CI

## Non-functional expectations

- Cross-user access returns **404** (same as missing rows) to avoid leaking primary-key existence
- Streaming import/export for scalability
- Documented limitations (scalar CSV fields, export-only vCard, CDN frontend)

See [REPORT.md](REPORT.md) and [TRACEABILITY.md](TRACEABILITY.md) for implementation mapping.
