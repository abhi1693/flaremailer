from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        database_auto_create=True,
        session_secret="test-session-secret-with-at-least-32-characters",
        cookie_secure=False,
        cors_origins="http://localhost:3000",
        worker_backoff_seconds="1,2,3",
        credential_encryption_key="test-credential-encryption-key-with-32-bytes",
    )


@pytest_asyncio.fixture
async def app(test_settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(test_settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


@pytest.fixture
def register_user() -> Any:
    async def register(api_client: httpx.AsyncClient) -> dict[str, Any]:
        response = await api_client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "correct-horse-battery"},
        )
        assert response.status_code == 201, response.text
        return response.json()["user"]

    return register


@pytest.fixture
def create_project() -> Any:
    async def create(api_client: httpx.AsyncClient, name: str = "Production") -> dict[str, Any]:
        response = await api_client.post("/api/v1/projects", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def add_verified_domain() -> Any:
    async def create(api_client: httpx.AsyncClient, project_id: str) -> dict[str, Any]:
        response = await api_client.post(
            f"/api/v1/projects/{project_id}/domains",
            json={"domain": "example.com", "verified": True, "active": True},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def configure_provider() -> Any:
    async def configure(
        api_client: httpx.AsyncClient,
        project_id: str,
        *,
        account_id: str = "account-default",
        api_token: str = "token-default-at-least-sixteen-characters",  # noqa: S107
    ) -> dict[str, Any]:
        response = await api_client.put(
            f"/api/v1/projects/{project_id}/credentials",
            json={"account_id": account_id, "api_token": api_token},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return configure


def email_payload(project_id: str | None = None, *, subject: str = "Welcome") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "from": {"email": "hello@example.com", "name": "Flaremailer"},
        "to": [{"email": "reader@example.net", "name": "Reader"}],
        "subject": subject,
        "html": "<strong>Hello</strong>",
        "text": "Hello",
        "tags": ["welcome"],
    }
    if project_id is not None:
        payload["project_id"] = project_id
    return payload
