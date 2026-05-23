# Testing

## Quick start

```powershell
python manage.py test
pytest
```

As of the latest run: **203 tests**, all passing (Django test runner and pytest).

## Coverage

Coverage is configured in [`pyproject.toml`](../pyproject.toml) under `[tool.coverage]`. It measures the `contacts` and `config` packages and omits migrations, test modules, and WSGI/ASGI entry points.

```powershell
coverage run manage.py test
coverage report
```

**Measured total: ~96%** on application code (`contacts` + `config`, excluding `prod.py`).

| Module | Cover | Notes |
|--------|-------|-------|
| `contacts/views.py` | 100% | HTMX branches, selection, bulk actions, import/export views |
| `contacts/importers.py` | 100% | Streaming CSV, header aliases, error report |
| `contacts/exporters.py` | 100% | CSV rows, vCard escape/fold/bulk |
| `contacts/admin.py` | 100% | Admin list displays and contact counts |
| `contacts/templatetags/querystring.py` | 100% | `sort_link`, `sort_indicator`, `qs_replace` |
| `contacts/models.py` | ~98% | Ownership, search, photo resize |
| `contacts/forms.py` | ~96% | CRUD forms, bulk/import validation |
| `config/settings/prod.py` | 0% | Not exercised in unit tests (expected) |

CI (`.github/workflows/ci.yml`) runs `coverage run manage.py test` and fails if total coverage drops below **85%**.

## Test layout

| File | Focus |
|------|-------|
| `test_auth.py` | Signup, login required, password reset form |
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
