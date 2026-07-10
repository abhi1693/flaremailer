from __future__ import annotations

import base64
import hashlib
import uuid

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

_CIPHERTEXT_VERSION = "v1"
_KEY_CONTEXT = b"flaremailer/project-provider-credentials/v1\x00"


class CredentialDecryptionError(ValueError):
    """Raised when stored credentials cannot be authenticated or decrypted."""


class CredentialCipher:
    """Encrypt provider tokens with a key derived from the platform secret."""

    def __init__(self, encryption_key: SecretStr | str, project_id: uuid.UUID) -> None:
        raw_key = (
            encryption_key.get_secret_value()
            if isinstance(encryption_key, SecretStr)
            else encryption_key
        )
        if len(raw_key.encode()) < 32:
            raise ValueError("CREDENTIAL_ENCRYPTION_KEY must be at least 32 bytes")
        derived_key = hashlib.sha256(_KEY_CONTEXT + project_id.bytes + raw_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived_key))

    def encrypt(self, plaintext: str) -> str:
        encrypted = self._fernet.encrypt(plaintext.encode()).decode()
        return f"{_CIPHERTEXT_VERSION}:{encrypted}"

    def decrypt(self, ciphertext: str) -> str:
        version, separator, payload = ciphertext.partition(":")
        if separator != ":" or version != _CIPHERTEXT_VERSION or not payload:
            raise CredentialDecryptionError("Unsupported credential ciphertext")
        try:
            return self._fernet.decrypt(payload.encode()).decode()
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise CredentialDecryptionError(
                "Credential ciphertext could not be authenticated"
            ) from exc
