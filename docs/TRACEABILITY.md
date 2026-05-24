# Requirements Traceability Matrix

Maps spec items from `Address Book Portal.txt` to implementation and tests.

> **Note:** See [SPEC.md](SPEC.md) for a committed requirements summary. The original `Address Book Portal.txt` may exist locally (gitignored).

| Requirement | Implementation | Tests |
|-------------|----------------|-------|
| Split settings (base/dev/prod) | `config/settings/` | `test_parses_standard_postgres_url`, `test_parses_url_encoded_credentials`, `test_prod_loads_with_required_env`, `test_prod_requires_secret_key` |
| Per-user ownership | `OwnedManager`, `get_for_user_or_404` | `test_manager_scopes_contacts_by_owner`, `test_group_rejects_cross_owner_contacts`, `test_tag_rejects_cross_owner_contacts` |
| Cross-user access returns 404 | `contacts/models.py`, mutating views | `test_cross_user_detail_returns_404`, `test_cross_user_edit_returns_403`, `test_cross_user_delete_returns_403`, `test_cross_user_vcard_returns_403`, `test_cross_user_purge_returns_403`, `test_contact_photo_cross_user_returns_404` |
| Signup / login / logout | Django auth + `contacts/signup_urls.py` | `test_signup_creates_user`, `test_auth_is_required_for_contact_list`, `test_logout_clears_bulk_selection`, `test_login_clears_selection_from_prior_user` |
| Password reset flow | `django.contrib.auth.urls` | `test_password_reset_form_renders` |
| Contact CRUD | `contacts/views.py`, forms, templates | `test_full_page_create_redirects_to_detail`, `test_edit_from_detail_via_htmx_redirects`, `test_contact_update_full_page` |
| HTMX modal CRUD | `_contact_form.html`, `_contact_form_fields.html` | `test_create_contact_via_htmx_on_list`, `test_create_contact_via_htmx_from_archive_refreshes_active_list`, `test_modal_create_form_posts_to_create_url` |
| Soft delete / archive | `Contact.soft_delete()`, archive list | `test_soft_delete_moves_contact_to_archive`, `test_archive_restore_keeps_archive_mode` |
| Sortable columns | `SORTS`, `sort_link`, `sort_indicator` | `test_contact_list_shows_sort_indicator` |
| Pagination (25) | `Paginator` in `list_context` | `test_contact_list_paginates` |
| Live HTMX search | `contact_list.html`, `#contact-table-body` | `test_htmx_search_returns_rows_partial` |
| Group / tag filters | `_filter_sidebar.html`, `base_contact_queryset` | `test_group_filter_limits_results`, `test_tag_filter_limits_results`, `test_base_contact_queryset_invalid_group_returns_empty` |
| Favorites view | `contact_list` mode `favorites` | `test_favorites_list_shows_only_favorites`, `test_favorites_list_excludes_archived_favorites` |
| Bulk selection + actions | session key, `bulk_action`, auth signals | `test_bulk_archive_soft_deletes`, `test_bulk_restore_from_archive`, `test_selection_page_select_all_on_page`, `test_select_all_partial_has_no_inline_click_handler` |
| Hand-rolled phone validation | `contacts/validators.py` | `test_normalizes_common_valid_numbers`, `test_rejects_invalid_numbers` |
| CSV import (streaming, partial) | `contacts/importers.py` | `test_csv_import_partially_succeeds_and_reports_row_errors`, `test_csv_import_requires_first_name`, `test_csv_import_page_warns_about_primary_fields_only`, `test_import_skips_duplicate_phone` |
| CSV import size limit | `CSVImportForm.clean_file` | `test_csv_import_rejects_oversized_file` |
| CSV export (streaming, primary fields) | `contacts/exporters.py` | `test_csv_export_yields_streaming_rows`, `test_csv_export_respects_active_filter`, `test_csv_export_includes_utf8_bom`, `test_safe_csv_cell_prefixes_formula_like_values` |
| vCard export | `contact_to_vcard`, `vcards_for_contacts` | `test_vcard_escapes_values_and_folds_long_lines`, `test_vcard_reference_shape`, `test_vcard_uid_uses_contact_uuid` |
| Photo upload + resize | `ContactForm`, `_resize_photo`, `validate_uploaded_photo` | `test_contact_form_rejects_oversized_photo`, `test_contact_form_rejects_invalid_photo_content_type`, `test_replaced_contact_photo_deletes_previous_file` |
| Dashboard stats / birthdays | `dashboard`, `contacts/utils.py` | `test_dashboard_renders`, `test_upcoming_birthdays_includes_leap_day_contacts` |
| Groups / tags CRUD | `organization`, `group_edit`, `tag_edit` | `test_duplicate_group_name_shows_form_error`, `test_organization_create_tag_success`, `test_group_edit_updates_name`, `test_tag_edit_updates_name_and_color` |
| Groups / tags on contact | `ContactForm.groups`, `ContactForm.tags` | `test_contact_form_assigns_groups_and_tags` |
| Single-contact purge | `contact_permanent_delete` | `test_archive_contact_can_be_purged`, `test_cross_user_purge_returns_403` |
| Selected export | `export_queryset` | `test_export_selected_only_when_requested`, `test_export_selected_empty_returns_header_only` |
| M2M ownership guard | `contacts/signals.py` | `test_group_rejects_cross_owner_contacts`, `test_tag_rejects_cross_owner_contacts` |
| ADRs | `docs/adr/` | — |
| Error report download | `csv_error_report` | `test_csv_error_report_keeps_session_until_next_import`, `test_csv_error_report_downloadable_twice` |
| Seed data | `contacts/fixtures/seed_data.json` | — |
| Logging | `config/settings/base.py` `LOGGING` | — |
| WhiteNoise static | `config/settings/prod.py` | `test_prod_loads_with_required_env` (subprocess) |
| Authenticated photo serving | `contact_photo`, `Contact.photo_url` | `test_contact_photo_returns_image_for_owner`, `test_contact_photo_cross_user_returns_404`, `test_direct_media_url_not_served` |
| Case-insensitive group/tag names | DB constraints + forms | `test_group_name_unique_case_insensitive`, `test_tag_name_unique_case_insensitive` |
| Django admin owner scoping | `contacts/admin.py` `OwnerScopedAdmin` | `test_contact_admin_scopes_queryset_for_staff`, `test_contact_admin_shows_all_for_superuser`, `test_related_contact_admin_scopes_contact_fk_for_staff` |

## Coverage note

Run `coverage run -m pytest -q && coverage report` for the current line-coverage percentage. See [TESTING.md](TESTING.md).

## Security note

See [SECURITY.md](SECURITY.md) for threat model and control mapping.

## Schema note

See [SCHEMA.md](SCHEMA.md) for entity relationships and constraints.
