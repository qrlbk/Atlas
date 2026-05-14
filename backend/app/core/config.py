from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:13000",
    "http://127.0.0.1:13000",
    "http://localhost:18080",
    "http://127.0.0.1:18080",
    "http://localhost:18090",
    "http://127.0.0.1:18090",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "development", "production"] = Field(
        default="development",
        description="When production, SECRET_KEY must not be the default.",
    )
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg2://atlas:atlas@db:5432/atlas"
    cors_origins: str = Field(
        default="",
        description="Comma-separated browser origins. Empty uses built-in local dev defaults.",
    )

    @model_validator(mode="after")
    def reject_default_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (not self.secret_key or self.secret_key == "change-me"):
            msg = "SECRET_KEY must be set to a secure non-default value when ENVIRONMENT=production"
            raise ValueError(msg)
        return self


settings = Settings()


def resolved_cors_origins() -> list[str]:
    raw = settings.cors_origins.strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return list(DEFAULT_CORS_ORIGINS)
