# Requirements Traceability Matrix

Maps spec items from `Address Book Portal.txt` to implementation and tests.

| Requirement | Implementation | Tests |
|-------------|----------------|-------|
| Split settings (base/dev/prod) | `config/settings/` | `test_postgres_from_url_*` |
| Per-user ownership | `OwnedManager`, `get_for_user_or_404` | `test_manager_scopes_contacts_by_owner`, `test_cross_user_*` |
| 403 on cross-user access | `contacts/models.py`, all mutating views | `test_cross_user_detail_returns_403`, `test_audit_fixes` (edit/delete/vCard/restore/favorite/org delete), `test_contact_photo_cross_user_returns_403` |
| Signup / login / logout | Django auth + `contacts/signup_urls.py` | `test_signup_creates_user`, `test_auth_is_required_for_contact_list`, `test_logout_clears_bulk_selection`, `test_login_clears_stale_bulk_selection` |
| Password reset flow | `django.contrib.auth.urls` | `test_password_reset_form_renders` |
| Contact CRUD | `contacts/views.py`, forms, templates | `test_full_page_create_redirects_to_detail`, `test_edit_from_detail_via_htmx_redirects` |
| HTMX modal CRUD | `_contact_form.html`, list/create/update views | `test_create_contact_via_htmx_on_list`, `test_create_contact_via_htmx_from_archive_refreshes_list`, `test_modal_create_form_posts_to_create_url` |
| Soft delete / archive | `Contact.soft_delete()`, archive list | `test_soft_delete_moves_contact_to_archive`, `test_archive_restore_keeps_archive_mode` |
| Sortable columns | `SORTS`, `sort_link`, `sort_indicator` | `test_contact_list_shows_sort_indicator` |
| Pagination (25) | `Paginator` in `list_context` | `test_contact_list_paginates` |
| Live HTMX search | `contact_list.html`, `#contact-table-body` | `test_htmx_search_returns_rows_partial` |
| Group / tag filters | `_filter_sidebar.html`, `base_contact_queryset` | `test_group_filter_limits_results`, `test_tag_filter_limits_results` |
| Favorites view | `contact_list` mode `favorites` | `test_favorites_list_shows_only_favorites`, `test_favorites_list_includes_archived_favorites` |
| Bulk selection + actions | session key, `bulk_action`, auth signals | `test_bulk_archive_soft_deletes`, `test_bulk_action_on_archive_only_affects_archived_selection`, `test_selection_toggle_preserves_page_query` |
| Hand-rolled phone validation | `contacts/validators.py` | `test_normalizes_common_valid_numbers`, `test_rejects_invalid_numbers` |
| CSV import (streaming, partial) | `contacts/importers.py` | `test_csv_import_partially_succeeds_and_reports_row_errors`, `test_csv_import_requires_first_name`, `test_csv_import_page_warns_about_primary_fields_only` |
| CSV import size limit | `CSVImportForm.clean_file` | `test_csv_import_rejects_oversized_file` |
| CSV export (streaming) | `contacts/exporters.py` | `test_csv_export_yields_streaming_rows`, `test_csv_export_respects_active_filter` |
| vCard export | `contact_to_vcard`, `vcards_for_contacts` | `test_vcard_escapes_values_and_folds_long_lines`, `test_vcard_reference_shape` |
| Photo upload + resize | `ContactForm`, `_resize_photo` | `test_contact_form_clears_photo` |
| Dashboard stats / birthdays | `dashboard`, `contacts/utils.py` | `test_dashboard_renders_metrics`, `test_upcoming_birthdays_includes_leap_day_contacts` |
| Groups / tags CRUD | `organization`, `GroupForm`, `TagForm` | `test_duplicate_group_name_shows_form_error`, `test_create_tag` |
| M2M ownership guard | `contacts/signals.py` | `test_group_rejects_cross_owner_contacts` |
| ADRs | `docs/adr/` | — |
| Error report download | `csv_error_report` | `test_csv_error_report_404_without_session`, `test_csv_error_report_download` |
| Seed data | `contacts/fixtures/seed_data.json` | — |
| Logging | `config/settings/base.py` `LOGGING` | — |
| WhiteNoise static | `config/settings/prod.py` | — |
| Authenticated photo serving | `contact_photo`, `Contact.photo_url` | `test_contact_photo_*` |
| Case-insensitive group/tag names | DB constraints + forms | `test_group_name_unique_case_insensitive`, `test_tag_name_unique_case_insensitive` |
| Django admin owner scoping | `contacts/admin.py` `OwnerScopedAdmin` | `test_contact_admin_scopes_queryset_for_staff`, `test_contact_admin_shows_all_for_superuser` |

## Coverage note

Run `coverage report` after `coverage run manage.py test` for the current line-coverage percentage. See [TESTING.md](TESTING.md).
