# ADR 0002: Hand-Rolled Phone Validation and vCard Generation

## Status

Accepted

## Context

The brief intentionally avoids `phonenumbers`, `vobject`, and similar packages. The required phone support is limited to E.164-style numbers and US 10-digit input. The vCard export only needs core vCard 3.0 fields ([RFC 2426](https://www.rfc-editor.org/rfc/rfc2426)).

## Decision

Implement a focused phone normalizer and a small vCard 3.0 ([RFC 2426](https://www.rfc-editor.org/rfc/rfc2426)) generator with escaping and UTF-8-aware line folding at 75 octets.

## Consequences

The dependency surface stays small and the behavior is easy to test. The tradeoff is narrower international phone validation and a deliberately small vCard feature subset.
