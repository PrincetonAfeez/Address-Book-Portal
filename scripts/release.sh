#!/usr/bin/env bash
# Release step: run before starting web workers (migrations + static assets).
set -euo pipefail
python manage.py migrate --noinput
python manage.py collectstatic --noinput
