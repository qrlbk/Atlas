import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_secret():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            secret_key="change-me",
            database_url="postgresql+psycopg2://x:y@localhost:1/db",
        )


def test_production_accepts_non_default_secret():
    s = Settings(
        environment="production",
        secret_key="a-secure-random-secret-at-least-32-chars-long",
        database_url="postgresql+psycopg2://x:y@localhost:1/db",
    )
    assert s.secret_key.startswith("a-secure")
