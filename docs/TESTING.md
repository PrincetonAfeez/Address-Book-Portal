# Testing

## Quick start

```powershell
python manage.py test
pytest
```

CI runs on push/PR via [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (badge in README). Locally, **pytest** is the canonical full suite.

## Last verified

| Field | Value |
|-------|-------|
| Commit | `dc63ef8` |
| Date | 2026-05-24 |
| Python | 3.12 |
| Django | 5.2.14 |
| Tests | **377 passed** (`pytest -q`) |
| Coverage | **95.0%** measured total (`coverage run -m pytest -q`; `prod.py` omitted) |

```bash
pytest -q
coverage run -m pytest -q && coverage report --fail-under=90
```

## Coverage

Coverage is configured in [`pyproject.toml`](../pyproject.toml) under `[tool.coverage]`. It measures the `contacts` and `config` packages and **omits**:

- migrations and test modules
- `manage.py`, `config/asgi.py`, `config/wsgi.py`
- **`config/settings/prod.py`** — not imported during dev/CI runs; validated separately via subprocess env tests in `config/tests/test_prod_settings.py`

Including `prod.py` in the denominator without executing it previously inflated “missing line” noise; omitting it aligns docs with reproducible totals.

| Module | Cover | Notes |
|--------|-------|-------|
| `contacts/views.py` | ~92% | HTMX branches, selection, bulk actions, import/export |
| `contacts/importers.py` | ~98% | Streaming CSV, duplicate skip, error cap |
| `contacts/exporters.py` | 100% | CSV rows (BOM + formula guard), vCard |
| `contacts/admin.py` | ~92% | Owner-scoped querysets, photo resize on save |
| `contacts/models.py` | ~99% | Ownership, search, photo resize, UUID |
| `contacts/forms.py` | ~92% | CRUD forms, photo validation, bulk/import |
| `config/settings/base.py` | 100% | Env helpers, logging setup |
| `config/settings/prod.py` | *(omitted)* | Subprocess settings validation tests only |

CI runs `coverage run manage.py test` and `pytest --collect-only`, failing below **90%** total coverage.

## Test layout

| File | Focus |
|------|-------|
| `test_auth.py` | Signup, login required, logout clears selection, password reset form |
| `test_audit_fixes.py` | Cross-user 404s, CSV UI, selection, admin-adjacent fixes |
| `test_select_all_ui.py` | **Rendered select-all partial** (no inverted `hx-on:click`) |
| `test_media_import_fixes.py` | Photo validation, CSV BOM, duplicate skip, vCard UUID |
| `test_dashboard.py` | Metrics, upcoming birthdays (leap-day) |
| `test_forms.py` | Photo clear, sync primary records, required fields |
| `test_forms_extended.py` | Signup, group/tag/bulk/import form validation |
| `test_import_export.py` | CSV/vCard streaming, partial import, formula export |
| `test_importers_unit.py` | Header aliases, date parsing, missing header |
| `test_exporters_unit.py` | vCard escape/fold, bulk export, scalar fallbacks |
| `test_models.py` | Ownership manager, soft delete, validation helpers |
| `test_models_extended.py` | 404 privacy, search, photo path, related models |
| `test_organization.py` | Groups/tags CRUD, delete, cross-owner guard |
| `test_signals.py` | M2M ownership validation, photo file cleanup |
| `test_admin.py` | Django admin registrations |
| `test_templatetags.py` | Sort link, sort indicator, querystring helper |
| `test_utils.py` | Birthday date math |
| `test_validators.py` | Phone normalization and rejection |
| `test_view_helpers.py` | View helper functions (selection, HTMX, queryset) |
| `test_views.py` | Core CRUD, HTMX list/detail, bulk actions, filters |
| `test_views_actions.py` | Selection, favorites, delete/restore, import view |
| `test_session_selection.py` | Session selection helper edge cases |
| `test_coverage_max.py` | Importers, exporters, forms, admin, view gaps |
| `test_integration.py` | Dashboard, detail, bulk tag/group, signals |
| `test_round_two_fixes.py` | Audit remediation: export, select-all POST, groups on form |
| `test_applied_fixes.py` | First audit pass regression tests |
| `config/tests/test_prod_settings.py` | Production settings env validation (subprocess) |
| `config/tests/test_database.py` | PostgreSQL URL parsing |

## Pytest

[`pytest`](https://docs.pytest.org/) with [`pytest-django`](https://pytest-django.readthedocs.io/) discovers all `test_*.py` modules. Configuration lives in [`pyproject.toml`](../pyproject.toml) under `[tool.pytest.ini_options]`.

```powershell
pip install -e ".[dev]"
pytest
pytest contacts/tests/test_select_all_ui.py -q
```

## UI vs server tests

- **Select-all:** `test_select_all_ui.py` asserts the rendered `_select_all_form.html` markup (hidden `selected` value, no `hx-on:click` on the checkbox). POST-only tests in `test_views_actions.py` do not execute HTMX attributes.
- **Browser E2E:** not required for CI; template assertions catch the inverted-handler class of bugs cheaply.

## Intentionally light coverage

- **Production settings module** — omitted from coverage totals; env contract tested in subprocess.
- **Media URLs** — photos use `/contacts/<id>/photo/` with ownership checks, not public `/media/` paths.

## Traceability

See [TRACEABILITY.md](TRACEABILITY.md) for requirement-to-test mapping against the project spec.
