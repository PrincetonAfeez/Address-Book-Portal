# Address Book Portal — Schema Files

This folder contains simple schema files for the Address Book Portal Django app.

## Files

- `contact.schema.json` — JSON Schema for contact records.
- `phone.schema.json` — JSON Schema for additional contact phone numbers.
- `email.schema.json` — JSON Schema for additional contact email addresses.
- `group.schema.json` — JSON Schema for contact groups.
- `tag.schema.json` — JSON Schema for contact tags.
- `database_schema.sql` — Simple relational database schema outline for the contacts app.

## Notes

- These schemas mirror the current `contacts` Django models at a practical level.
- `owner_id` represents the authenticated Django user who owns the record.
- `group_ids` and `tag_ids` represent many-to-many relationships between contacts and groups/tags.
- Blank Django fields are represented as optional strings with max-length limits.
- Timestamp fields are included as read-only values because Django manages them automatically.
