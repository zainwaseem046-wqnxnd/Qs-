"""Application configuration.

All configuration is read from environment variables (optionally a local `.env` file in development).
Secrets are never hard-coded: the application refuses to start outside `development`/`test` if
security-critical secrets are left at insecure defaults.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEV_SECRET = "dev-only-insecure-secret-change-me-0123456789abcdef"  # noqa: S105
# Fernet key used ONLY in development/test. Production must supply its own.
_INSECURE_DEV_FERNET = "q0nV9yQe0n3j7cQkqN0bQ2m2b0f0rM7Qf0dWm7mZ0kE="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="QS_", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "QS Intelligence USA"

    # Runtime connection: a NON-owner role that is subject to Row-Level Security.
    database_url: str = "postgresql+psycopg://qs_app:qs_app_dev@localhost:5432/qs_dev"
    # Migration connection: the schema-owner role. Never used by the running API.
    migration_database_url: str = "postgresql+psycopg://qs_owner:qs_owner_dev@localhost:5432/qs_dev"
    # Name of the runtime role that migrations grant privileges to.
    app_db_role: str = "qs_app"

    redis_url: str | None = "redis://localhost:6379/0"

    jwt_secret: str = _INSECURE_DEV_SECRET
    jwt_issuer: str = "qs-intelligence"
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 14 * 24 * 60 * 60
    mfa_challenge_ttl_seconds: int = 5 * 60
    invitation_ttl_seconds: int = 7 * 24 * 60 * 60

    # Fernet key for encrypting secrets at rest (e.g. TOTP seeds).
    field_encryption_key: str = _INSECURE_DEV_FERNET

    cookie_secure: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    public_app_url: str = "http://localhost:3000"

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./var/storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    max_upload_bytes: int = 100 * 1024 * 1024

    rate_limit_enabled: bool = True
    login_rate_limit_per_minute: int = 10

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> Settings:
        if self.environment in ("staging", "production"):
            if self.jwt_secret == _INSECURE_DEV_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("QS_JWT_SECRET must be set to a strong secret outside development")
            if self.field_encryption_key == _INSECURE_DEV_FERNET:
                raise ValueError("QS_FIELD_ENCRYPTION_KEY must be set outside development")
            if not self.cookie_secure:
                raise ValueError("QS_COOKIE_SECURE must be true outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
