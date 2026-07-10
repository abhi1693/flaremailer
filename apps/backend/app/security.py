from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings

_password_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)
_slug_pattern = re.compile(r"[^a-z0-9]+")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def make_session_token(user_id: str, settings: Settings) -> str:
    serializer = URLSafeTimedSerializer(
        settings.session_secret.get_secret_value(), salt="flaremailer-session-v1"
    )
    return serializer.dumps({"user_id": user_id, "version": 1})


def read_session_token(token: str, settings: Settings) -> str | None:
    serializer = URLSafeTimedSerializer(
        settings.session_secret.get_secret_value(), salt="flaremailer-session-v1"
    )
    try:
        payload: dict[str, Any] = serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    user_id = payload.get("user_id")
    if payload.get("version") != 1 or not isinstance(user_id, str):
        return None
    return user_id


def generate_api_key() -> tuple[str, str, str]:
    plaintext = f"fm_live_{secrets.token_urlsafe(32)}"
    return plaintext, plaintext[:20], hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_public_email_id() -> str:
    return f"email_{secrets.token_urlsafe(18)}"


def slugify(value: str, *, fallback: str = "project") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = _slug_pattern.sub("-", normalized.lower()).strip("-")
    return (slug or fallback)[:64]
