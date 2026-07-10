from __future__ import annotations

from typing import Any

import httpx

from tests.conftest import email_payload


async def test_enqueue_idempotency_activity_and_api_key_auth(
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])

    response = await client.post(
        "/api/v1/emails",
        json=email_payload(project["id"]),
        headers={"Idempotency-Key": "signup-123"},
    )
    assert response.status_code == 202, response.text
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["deduplicated"] is False

    duplicate = await client.post(
        "/api/v1/emails",
        json=email_payload(project["id"]),
        headers={"Idempotency-Key": "signup-123"},
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == queued["id"]
    assert duplicate.json()["deduplicated"] is True

    conflict = await client.post(
        "/api/v1/emails",
        json=email_payload(project["id"], subject="Different"),
        headers={"Idempotency-Key": "signup-123"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"

    activity = await client.get("/api/v1/emails", params={"project_id": project["id"]})
    assert activity.status_code == 200
    assert activity.json()["total"] == 1
    detail = await client.get(
        f"/api/v1/emails/{queued['id']}", params={"project_id": project["id"]}
    )
    assert detail.status_code == 200
    assert detail.json()["html"] == "<strong>Hello</strong>"

    key_response = await client.post(
        f"/api/v1/projects/{project['id']}/api-keys", json={"name": "SDK"}
    )
    api_key = key_response.json()["plaintext"]
    api_client = httpx.AsyncClient(
        transport=client._transport,  # type: ignore[attr-defined]
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        by_key = await api_client.post("/api/v1/emails", json=email_payload())
        assert by_key.status_code == 202, by_key.text
        key_activity = await api_client.get("/api/v1/emails")
        assert key_activity.status_code == 200
        assert key_activity.json()["total"] == 2
    finally:
        await api_client.aclose()

    metrics = await client.get("/api/v1/metrics", params={"project_id": project["id"]})
    assert metrics.status_code == 200
    assert metrics.json()["queued"] == 2


async def test_sender_gate_template_escape_and_suppression(
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
) -> None:
    await register_user(client)
    project = await create_project(client)

    blocked = await client.post("/api/v1/emails", json=email_payload(project["id"]))
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "sender_domain_not_verified"
    await add_verified_domain(client, project["id"])

    template_response = await client.post(
        f"/api/v1/projects/{project['id']}/templates",
        json={
            "name": "Greeting",
            "subject": "Hello {{ name }}",
            "html": "<p>{{ unsafe }}</p>",
            "text": "Hello {{ name }}",
        },
    )
    assert template_response.status_code == 201, template_response.text
    template = template_response.json()

    preview = await client.post(
        f"/api/v1/projects/{project['id']}/templates/{template['id']}/preview",
        json={"variables": {"name": "Ada", "unsafe": "<script>alert(1)</script>"}},
    )
    assert preview.status_code == 200
    assert preview.json()["subject"] == "Hello Ada"
    assert "<script>" not in preview.json()["html"]
    assert "&lt;script&gt;" in preview.json()["html"]

    missing_variable = await client.post(
        f"/api/v1/projects/{project['id']}/templates/{template['id']}/preview",
        json={"variables": {"name": "Ada"}},
    )
    assert missing_variable.status_code == 422

    suppression = await client.post(
        f"/api/v1/projects/{project['id']}/suppressions",
        json={"email": "reader@example.net", "reason": "complaint"},
    )
    assert suppression.status_code == 201

    template_send = email_payload(project["id"])
    template_send.pop("subject")
    template_send.pop("html")
    template_send.pop("text")
    template_send["template_id"] = template["id"]
    template_send["variables"] = {"name": "Ada", "unsafe": "<b>safe text</b>"}
    suppressed = await client.post("/api/v1/emails", json=template_send)
    assert suppressed.status_code == 202, suppressed.text
    assert suppressed.json()["status"] == "suppressed"
    assert suppressed.json()["suppressed_recipients"] == ["reader@example.net"]
