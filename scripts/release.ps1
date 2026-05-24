# Release step: run before starting web workers (migrations + static assets).
$ErrorActionPreference = "Stop"
python manage.py migrate --noinput
python manage.py collectstatic --noinput
