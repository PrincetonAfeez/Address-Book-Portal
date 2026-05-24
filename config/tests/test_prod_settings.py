""" Test production settings """

import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProdSettingsTests(SimpleTestCase):
    def _load_prod(self, env):
        code = """
import importlib
import os
import sys
from pathlib import Path
root = Path({root!r})
sys.path.insert(0, str(root))
os.environ.update({env!r})
for key in list(os.environ.keys()):
    if key.startswith("DJANGO_") or key in {{"DATABASE_URL", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"}}:
        if key not in {env!r}:
            os.environ.pop(key, None)
import config.settings.prod as prod
importlib.reload(prod)
print("OK")
""".format(root=str(PROJECT_ROOT), env=env)
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

    def test_prod_requires_secret_key(self):
        result = self._load_prod(
            {
                "DJANGO_ALLOWED_HOSTS": "example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr + result.stdout)

    def test_prod_requires_allowed_hosts(self):
        result = self._load_prod(
            {
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr + result.stdout)

    def test_prod_requires_csrf_trusted_origins(self):
        result = self._load_prod(
            {
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_ALLOWED_HOSTS": "example.com",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr + result.stdout)

    def test_prod_loads_with_required_env(self):
        result = self._load_prod(
            {
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_ALLOWED_HOSTS": "example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_prod_uses_database_url_when_set(self):
        result = self._load_prod(
            {
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_ALLOWED_HOSTS": "example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
                "DATABASE_URL": "postgres://user:pass@localhost:5432/appdb",
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prod_hsts_subdomains_and_preload_are_configurable(self):
        code = """
import os, sys
from pathlib import Path
root = Path({root!r})
sys.path.insert(0, str(root))
os.environ.update({env!r})
for key in list(os.environ.keys()):
    if key.startswith("DJANGO_") and key not in {env!r}:
        os.environ.pop(key, None)
import importlib
import config.settings.prod as prod
importlib.reload(prod)
assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
assert prod.SECURE_HSTS_PRELOAD is True
print("OK")
""".format(
            root=str(PROJECT_ROOT),
            env={
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_ALLOWED_HOSTS": "example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
                "DJANGO_HSTS_INCLUDE_SUBDOMAINS": "true",
                "DJANGO_HSTS_PRELOAD": "true",
            },
        )
        check = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("OK", check.stdout)


class BaseSettingsTests(SimpleTestCase):
    def test_env_bool_defaults_false_for_missing_value(self):
        from config.settings.base import env_bool

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env_bool("MISSING_FLAG"))

    def test_env_bool_parses_truthy_values(self):
        from config.settings.base import env_bool

        with patch.dict(os.environ, {"FLAG": "true"}):
            self.assertTrue(env_bool("FLAG"))
