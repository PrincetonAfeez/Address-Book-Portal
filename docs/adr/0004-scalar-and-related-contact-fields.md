# ADR 0004: Scalar and Related Contact Fields

## Status

Accepted

## Context

Contacts need a primary phone and email for simple forms, CSV import, and vCard export. The spec also describes one-to-many `Phone` and `Email` models for labeled values (mobile, work, home).

Supporting both shapes creates duplication: `Contact.phone` / `Contact.email` coexist with related `Phone` / `Email` rows.

## Decision

Keep **scalar primary fields** on `Contact` for the v1 UI and import path. Mirror those values into related `Phone` (mobile) and `Email` (other) records via `ContactForm.sync_primary_records()` after save.

The related models remain in place for:

- vCard multi-value export
- Admin inlines
- Future multi-phone UI without a migration

## Consequences

- The v1 UI edits only primary scalar fields; detail pages also list related records.
- Search matches both scalar fields and related rows.
- Admin or shell can add extra labeled phones/emails that the form does not surface.
- Rows mirrored from scalar fields are marked `is_scalar_sync=True`; sync only updates or removes those rows, leaving other labeled phones/emails intact.
- A future version can drop scalars or add formsets once multi-value editing is required.
