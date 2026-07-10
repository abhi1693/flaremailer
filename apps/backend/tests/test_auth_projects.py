from __future__ import annotations

from typing import Any

import httpx


async def test_registration_session_project_and_one_time_api_key(
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
) -> None:
    health = await client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    unauthorized = await client.get("/api/v1/projects")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "authentication_required"

    missing_route = await client.get("/not-a-route")
    assert missing_route.status_code == 404
    assert missing_route.json()["error"]["code"] == "http_error"

    user = await register_user(client)
    assert user["email"] == "owner@example.com"
    cookie = client.cookies.get("flaremailer_session")
    assert cookie

    current = await client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["user"]["id"] == user["id"]

    project = await create_project(client)
    assert project["slug"] == "production"
    duplicate_name = await create_project(client)
    assert duplicate_name["slug"] == "production-2"

    created_key = await client.post(
        f"/api/v1/projects/{project['id']}/api-keys", json={"name": "CI"}
    )
    assert created_key.status_code == 201
    plaintext = created_key.json()["plaintext"]
    assert plaintext.startswith("fm_live_")

    listed_keys = await client.get(f"/api/v1/projects/{project['id']}/api-keys")
    assert listed_keys.status_code == 200
    assert listed_keys.json()["items"][0]["prefix"] == plaintext[:20]
    assert "plaintext" not in listed_keys.json()["items"][0]

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_login_rejects_bad_password(client: httpx.AsyncClient, register_user: Any) -> None:
    await register_user(client)
    await client.post("/api/v1/auth/logout")
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "not-the-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"
