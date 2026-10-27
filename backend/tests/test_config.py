import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@host.neon.tech/db?sslmode=require", "postgresql+psycopg://u:p@host.neon.tech/db?sslmode=require"),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@localhost/db", "postgresql+psycopg://u:p@localhost/db"),
    ],
)
def test_hosted_database_urls_use_the_psycopg3_driver(given, expected):
    settings = Settings(database_url=given, jwt_secret_key="x" * 40)
    assert settings.database_url == expected
