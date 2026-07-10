from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from app.credentials import CredentialCipher, CredentialDecryptionError
from app.models import ProjectProviderCredentials


async def test_project_credentials_crud_encrypts_and_never_discloses_token(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    test_settings: Any,
) -> None:
    unauthorized = await client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000001/credentials"
    )
    assert unauthorized.status_code == 401

    await register_user(client)
    project = await create_project(client)
    endpoint = f"/api/v1/projects/{project['id']}/credentials"

    empty = await client.get(endpoint)
    assert empty.status_code == 200
    assert empty.json() == {
        "configured": False,
        "account_id": None,
        "token_last_four": None,
        "updated_at": None,
    }

    missing_initial_token = await client.put(endpoint, json={"account_id": "account-1"})
    assert missing_initial_token.status_code == 422
    assert missing_initial_token.json()["error"]["code"] == "api_token_required"

    short_token = await client.put(
        endpoint,
        json={"account_id": "account-1", "api_token": "too-short"},
    )
    assert short_token.status_code == 422
    assert "too-short" not in short_token.text

    plaintext = "cloudflare-secret-token-that-must-stay-private"
    created = await client.put(
        endpoint,
        json={"account_id": "account-1", "api_token": plaintext},
    )
    assert created.status_code == 200
    assert created.json()["configured"] is True
    assert created.json()["account_id"] == "account-1"
    assert created.json()["token_last_four"] == "vate"  # noqa: S105
    assert "api_token" not in created.json()
    assert plaintext not in created.text

    fetched = await client.get(endpoint)
    assert fetched.status_code == 200
    assert fetched.json() == created.json()
    assert plaintext not in fetched.text

    async with app.state.session_factory() as session:
        stored = await session.get(ProjectProviderCredentials, uuid.UUID(project["id"]))
        assert stored is not None
        original_ciphertext = stored.api_token_encrypted
        assert plaintext not in original_ciphertext
        decrypted = CredentialCipher(
            test_settings.credential_encryption_key, stored.project_id
        ).decrypt(original_ciphertext)
        assert decrypted == plaintext

    account_only_update = await client.put(endpoint, json={"account_id": "account-2"})
    assert account_only_update.status_code == 200
    assert account_only_update.json()["account_id"] == "account-2"
    assert account_only_update.json()["token_last_four"] == "vate"  # noqa: S105
    async with app.state.session_factory() as session:
        stored = await session.get(ProjectProviderCredentials, uuid.UUID(project["id"]))
        assert stored is not None
        assert stored.api_token_encrypted == original_ciphertext

    removed = await client.delete(endpoint)
    assert removed.status_code == 204
    assert (await client.get(endpoint)).json()["configured"] is False


async def test_project_credentials_are_owner_scoped(
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await client.post("/api/v1/auth/logout")
    second_registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct-horse-battery"},
    )
    assert second_registration.status_code == 201

    response = await client.get(f"/api/v1/projects/{project['id']}/credentials")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_encrypted_token_is_bound_to_its_project(test_settings: Any) -> None:
    first_project = uuid.uuid4()
    second_project = uuid.uuid4()
    ciphertext = CredentialCipher(test_settings.credential_encryption_key, first_project).encrypt(
        "cloudflare-secret-token"
    )

    with pytest.raises(CredentialDecryptionError):
        CredentialCipher(test_settings.credential_encryption_key, second_project).decrypt(
            ciphertext
        )
