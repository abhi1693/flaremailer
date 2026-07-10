from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from the process environment."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Flaremailer API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://flaremailer:flaremailer@localhost:5432/flaremailer"
    database_echo: bool = False
    database_auto_create: bool = False

    session_secret: SecretStr = SecretStr("development-only-change-me-32-bytes")
    session_cookie_name: str = "flaremailer_session"
    session_max_age_seconds: int = Field(default=60 * 60 * 24 * 14, ge=300, le=60 * 60 * 24 * 90)
    cookie_secure: bool = False
    cookie_domain: str | None = None

    cors_origins: str = "http://localhost:3000"
    max_request_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)

    credential_encryption_key: SecretStr = SecretStr(
        "development-only-provider-credential-key-change-me"
    )
    cloudflare_api_base_url: str = "https://api.cloudflare.com/client/v4"
    cloudflare_timeout_seconds: float = Field(default=15.0, gt=0, le=60)

    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    worker_batch_size: int = Field(default=20, ge=1, le=100)
    worker_lock_timeout_seconds: int = Field(default=300, ge=30, le=3600)
    worker_max_attempts: int = Field(default=4, ge=1, le=10)
    worker_backoff_seconds: str = "5,30,120"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.environment.lower() in {"production", "prod"}:
            secret = self.session_secret.get_secret_value()
            weak_markers = ("development-only", "replace-with", "change-me", "changeme")
            has_weak_marker = any(marker in secret.lower() for marker in weak_markers)
            if len(secret.encode()) < 32 or has_weak_marker:
                raise ValueError(
                    "SESSION_SECRET must be a non-placeholder value of at least 32 bytes"
                )
            credential_key = self.credential_encryption_key.get_secret_value()
            credential_key_is_weak = any(
                marker in credential_key.lower() for marker in weak_markers
            )
            if len(credential_key.encode()) < 32 or credential_key_is_weak:
                raise ValueError(
                    "CREDENTIAL_ENCRYPTION_KEY must be a non-placeholder value of at least 32 bytes"
                )
            if not self.database_url.startswith("postgresql+"):
                raise ValueError("PostgreSQL is required in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def worker_backoff_schedule(self) -> tuple[int, ...]:
        values = tuple(int(value.strip()) for value in self.worker_backoff_seconds.split(","))
        if not values or any(value < 1 for value in values):
            raise ValueError("WORKER_BACKOFF_SECONDS must contain positive integers")
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
