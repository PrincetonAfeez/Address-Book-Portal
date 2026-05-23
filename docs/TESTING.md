# Testing

## Quick start

```powershell
python manage.py test
pytest
```

As of the latest run: **319 tests**, all passing. CI uses the Django test runner with coverage; run `pytest` locally for the same suite.

## Coverage

Coverage is configured in [`pyproject.toml`](../pyproject.toml) under `[tool.coverage]`. It measures the `contacts` and `config` packages and omits migrations, test modules, and WSGI/ASGI entry points.

```powershell
coverage run manage.py test
coverage report
```

**Measured total: ~97.5%** on application code (`contacts` + `config`, excluding `prod.py`).

| Module | Cover | Notes |
|--------|-------|-------|
| `contacts/views.py` | 100% | HTMX branches, selection, bulk actions, import/export views |
| `contacts/importers.py` | 100% | Streaming CSV, header aliases, error report |
| `contacts/exporters.py` | 100% | CSV rows, vCard escape/fold/bulk |
| `contacts/admin.py` | ~96% | Owner-scoped querysets, superuser vs staff fieldsets |
| `contacts/templatetags/querystring.py` | 100% | `sort_link`, `sort_indicator`, `qs_replace` |
| `contacts/models.py` | 100% | Ownership, search, photo resize |
| `contacts/forms.py` | 100% | CRUD forms, bulk/import validation |
| `config/database.py` | 100% | `postgres_from_url` parsing |
| `config/settings/base.py` | 100% | Env helpers, logging setup |
| `config/settings/prod.py` | 0% | Validated via subprocess env tests only |

CI (`.github/workflows/ci.yml`) runs `coverage run manage.py test` once and fails if total coverage drops below **85%**. Use `pytest` locally for the same test modules.

## Test layout

| File | Focus |
|------|-------|
| `test_auth.py` | Signup, login required, logout clears selection, password reset form |
| `test_audit_fixes.py` | Cross-user 403s, CSV UI, selection, admin-adjacent fixes |
| `test_dashboard.py` | Metrics, upcoming birthdays (leap-day) |
| `test_forms.py` | Photo clear, sync primary records, required fields |
| `test_forms_extended.py` | Signup, group/tag/bulk/import form validation |
| `test_import_export.py` | CSV/vCard streaming, partial import, size limit |
| `test_importers_unit.py` | Header aliases, date parsing, missing header |
| `test_exporters_unit.py` | vCard escape/fold, bulk export, scalar fallbacks |
| `test_models.py` | Ownership manager, soft delete |
| `test_models_extended.py` | 403/404, search, photo path, related models |
| `test_organization.py` | Groups/tags CRUD, delete, cross-owner guard |
| `test_signals.py` | M2M ownership validation on tags |
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
| `test_final_coverage.py` | Remaining branch coverage (admin, UTF-8, logging) |
| `config/tests/test_prod_settings.py` | Production settings env validation |
| `config/tests/test_database.py` | PostgreSQL URL parsing |

## Pytest

[`pytest`](https://docs.pytest.org/) with [`pytest-django`](https://pytest-django.readthedocs.io/) discovers all `test_*.py` modules. Configuration lives in [`pyproject.toml`](../pyproject.toml) under `[tool.pytest.ini_options]`.

```powershell
pip install -e ".[dev]"
pytest
pytest contacts/tests/test_views_actions.py -k favorite
```

## Intentionally light coverage

- **Production settings** — `config.settings.prod` is validated by deployment configuration, not unit tests.
- **Media URLs** — photos use `/contacts/<id>/photo/` with ownership checks, not public `/media/` paths.

## Traceability

See [TRACEABILITY.md](TRACEABILITY.md) for requirement-to-test mapping against the project spec.
