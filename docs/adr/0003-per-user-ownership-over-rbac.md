# ADR 0003: Per-User Ownership Over RBAC

## Status

Accepted

## Context

Version 1 is a personal address book. Every contact, group, and tag belongs to one authenticated user.

## Decision

Use per-row ownership with a foreign key to Django's user model instead of introducing roles, teams, or organization-level permissions.

## Consequences

The model is simple, secure, and easy to reason about for a single-tenant product. If shared address books become necessary, the ownership layer can evolve toward organizations or RBAC with clearer requirements.
