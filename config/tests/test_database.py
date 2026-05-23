from django.test import SimpleTestCase

from config.database import postgres_from_url


class PostgresFromUrlTests(SimpleTestCase):
    def test_parses_standard_postgres_url(self):
        config = postgres_from_url("postgres://user:secret@db.example.com:5433/myapp")
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "myapp")
        self.assertEqual(config["USER"], "user")
        self.assertEqual(config["PASSWORD"], "secret")
        self.assertEqual(config["HOST"], "db.example.com")
        self.assertEqual(config["PORT"], "5433")
        self.assertEqual(config["OPTIONS"], {})

    def test_parses_url_encoded_credentials(self):
        config = postgres_from_url("postgres://user%40corp:p%40ss%2Fword@localhost/app")
        self.assertEqual(config["USER"], "user@corp")
        self.assertEqual(config["PASSWORD"], "p@ss/word")

    def test_includes_sslmode_from_query_string(self):
        config = postgres_from_url(
            "postgres://user:pass@localhost:5432/app?sslmode=require"
        )
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})
