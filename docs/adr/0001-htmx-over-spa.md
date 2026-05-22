# ADR 0001: HTMX Over a JavaScript SPA

## Status

Accepted

## Context

The product needs fast CRUD, search, pagination, modal forms, and inline actions. It does not need offline behavior, complex client state, or a heavily interactive canvas.

## Decision

Use Django templates with HTMX for partial updates.

## Consequences

The app keeps Django as the main rendering and authorization boundary, avoids a separate API layer, and still gets live search, modal forms, and out-of-band counter updates. If the interface grows into deep client-side state, a richer frontend can be introduced later around proven screens.
