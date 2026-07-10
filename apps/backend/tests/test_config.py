from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

PRODUCTION_SETTINGS = {
    "environment": "production",
    "database_url": "postgresql+asyncpg://user:password@localhost:5432/flaremailer",
    "cookie_secure": True,
    "credential_encryption_key": "b" * 64,
}


@pytest.mark.parametrize(
    "secret",
    [
        "too-short",
        "replace-with-at-least-32-random-characters",
        "development-only-but-long-enough-to-pass-length",
    ],
)
def test_production_rejects_weak_session_secrets(secret: str) -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        Settings(session_secret=secret, **PRODUCTION_SETTINGS)


def test_production_accepts_a_strong_session_secret() -> None:
    settings = Settings(session_secret="a" * 64, **PRODUCTION_SETTINGS)

    assert settings.session_secret.get_secret_value() == "a" * 64


def test_production_rejects_weak_credential_encryption_key() -> None:
    with pytest.raises(ValidationError, match="CREDENTIAL_ENCRYPTION_KEY"):
        Settings(
            session_secret="a" * 64,
            **{**PRODUCTION_SETTINGS, "credential_encryption_key": "development-only-key"},
        )
