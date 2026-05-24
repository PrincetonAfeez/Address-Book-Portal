# Deployment

How this project is deployed for academic demos and what to change for production polish.

## Reproducible dependencies

| File | Purpose |
|------|---------|
| `pyproject.toml` | Version ranges for library-style installs |
| `requirements.txt` | Production ranges (Railway/minimal pip) |
| `requirements-lock.txt` | **Pinned versions** verified with the test suite |

```bash
pip install -r requirements-lock.txt
```

## Hosting configs (same behavior, two platforms)

| File | Platform | Release (migrate + static) | Web |
|------|----------|----------------------------|-----|
| `railway.json` | Railway | `preDeployCommand` | `startCommand` → Gunicorn |
| `Procfile` | Heroku-style | `release:` process | `web:` → Gunicorn |

Both intentionally mirror the same steps so they do not drift. Prefer **one** platform in production; keep both files only because the course supports Railway and generic PaaS Procfiles.

Manual release (any host):

```bash
./scripts/release.sh
# or: pwsh scripts/release.ps1
```

## Railway simplification (historical)

Earlier configs ran `migrate && collectstatic && gunicorn` in a single start command. That works for student projects but runs migrations on every dyno restart. Current configs use a **release/pre-deploy** phase for migrations and static collection, then start Gunicorn only.

## Required production environment

See `.env.example` and [SECURITY.md](SECURITY.md). Minimum:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` (PostgreSQL)

Optional HSTS tuning (defaults are conservative for demo domains):

- `DJANGO_HSTS_SECONDS` (default `31536000`; set `0` to disable HSTS)
- `DJANGO_HSTS_INCLUDE_SUBDOMAINS` (default `false`)
- `DJANGO_HSTS_PRELOAD` (default `false`)

## Media / contact photos (documented limitation)

Contact photos are stored on **local disk** (`MEDIA_ROOT`). On ephemeral PaaS hosts, redeploys or restarts can **lose uploaded files** unless you add object storage (S3-compatible backend, Cloudinary, etc.).

The app serves photos through `/contacts/<id>/photo/` with login and ownership checks — not as public `/media/` URLs. For a graded demo, document this limitation rather than requiring cloud storage.

See [REPORT.md](REPORT.md) limitations §3.

## Static files

WhiteNoise serves collected static assets in production (`collectstatic` in the release step). CDN frontend libraries (Tailwind, HTMX, Lucide) still load from external CDNs — see [SECURITY.md](SECURITY.md).
