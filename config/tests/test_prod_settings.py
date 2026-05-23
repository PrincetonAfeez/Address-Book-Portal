from urllib.parse import quote

from django.test import SimpleTestCase

from config.database import postgres_from_url


class PostgresUrlTests(SimpleTestCase):
    def test_postgres_from_url_unquotes_credentials_and_sslmode(self):
        password = "p@ss%word"
        url = (
            f"postgres://user:{quote(password, safe='')}@db.example.com:5432/mydb"
            "?sslmode=require"
        )
        config = postgres_from_url(url)

        self.assertEqual(config["USER"], "user")
        self.assertEqual(config["PASSWORD"], password)
        self.assertEqual(config["NAME"], "mydb")
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")
