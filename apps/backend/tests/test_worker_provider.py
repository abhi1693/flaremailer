from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select, update

from app.config import Settings
from app.models import DeliveryAttempt, EmailMessage
from app.providers.base import (
    EmailProvider,
    OutboundMessage,
    ProviderCredentials,
    ProviderError,
    ProviderResult,
)
from app.providers.cloudflare import CloudflareEmailProvider
from app.worker import claim_due_messages, process_message
from tests.conftest import email_payload


class FakeProvider(EmailProvider):
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.messages: list[OutboundMessage] = []
        self.credentials: list[ProviderCredentials] = []

    async def send(
        self, message: OutboundMessage, credentials: ProviderCredentials
    ) -> ProviderResult:
        self.messages.append(message)
        self.credentials.append(credentials)
        if self.failures > 0:
            self.failures -= 1
            raise ProviderError("throttled", code="provider_http_429", retriable=True)
        return ProviderResult(
            message_id="cf-message-1",
            raw_response={"success": True, "result": {"message_id": "cf-message-1"}},
        )

    async def aclose(self) -> None:
        return None


async def test_worker_records_success_and_attempt(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await configure_provider(client, project["id"])
    enqueue = await client.post("/api/v1/emails", json=email_payload(project["id"]))
    public_id = enqueue.json()["id"]

    claimed = await claim_due_messages(app.state.session_factory, test_settings)
    assert len(claimed) == 1
    provider = FakeProvider()
    await process_message(app.state.session_factory, provider, test_settings, claimed[0])

    async with app.state.session_factory() as session:
        message = await session.scalar(
            select(EmailMessage).where(EmailMessage.public_id == public_id)
        )
        assert message is not None
        attempts = list(
            await session.scalars(
                select(DeliveryAttempt).where(DeliveryAttempt.message_id == message.id)
            )
        )
    assert message.status == "sent"
    assert message.provider_message_id == "cf-message-1"
    assert message.attempt_count == 1
    assert len(attempts) == 1
    assert attempts[0].status == "sent"
    assert provider.messages[0].bcc == []

    resend = await client.post(
        f"/api/v1/emails/{public_id}/resend", params={"project_id": project["id"]}
    )
    assert resend.status_code == 202, resend.text
    resent_detail = await client.get(
        f"/api/v1/emails/{resend.json()['id']}", params={"project_id": project["id"]}
    )
    assert resent_detail.status_code == 200
    assert resent_detail.json()["resend_of_id"] == public_id


async def test_worker_retries_then_succeeds(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await configure_provider(client, project["id"])
    await client.post("/api/v1/emails", json=email_payload(project["id"]))
    provider = FakeProvider(failures=1)

    first = (await claim_due_messages(app.state.session_factory, test_settings))[0]
    await process_message(app.state.session_factory, provider, test_settings, first)
    async with app.state.session_factory() as session, session.begin():
        message = await session.get(EmailMessage, first)
        assert message is not None
        assert message.status == "queued"
        assert message.error_code == "provider_http_429"
        await session.execute(
            update(EmailMessage).where(EmailMessage.id == first).values(next_attempt_at=None)
        )

    second = (await claim_due_messages(app.state.session_factory, test_settings))[0]
    await process_message(app.state.session_factory, provider, test_settings, second)
    async with app.state.session_factory() as session:
        message = await session.get(EmailMessage, first)
        attempts = list(
            await session.scalars(
                select(DeliveryAttempt)
                .where(DeliveryAttempt.message_id == first)
                .order_by(DeliveryAttempt.attempt_number)
            )
        )
    assert message is not None
    assert message.status == "sent"
    assert message.attempt_count == 2
    assert [attempt.status for attempt in attempts] == ["failed", "sent"]


async def test_worker_records_terminal_failure(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await configure_provider(client, project["id"])
    await client.post("/api/v1/emails", json=email_payload(project["id"]))
    message_id = (await claim_due_messages(app.state.session_factory, test_settings))[0]

    class RejectedProvider(FakeProvider):
        async def send(
            self, message: OutboundMessage, credentials: ProviderCredentials
        ) -> ProviderResult:
            self.messages.append(message)
            self.credentials.append(credentials)
            raise ProviderError(
                "recipient rejected", code="provider_permanent_bounce", retriable=False
            )

    await process_message(app.state.session_factory, RejectedProvider(), test_settings, message_id)
    async with app.state.session_factory() as session:
        message = await session.get(EmailMessage, message_id)
        attempt = await session.scalar(
            select(DeliveryAttempt).where(DeliveryAttempt.message_id == message_id)
        )
    assert message is not None
    assert message.status == "failed"
    assert message.error_code == "provider_permanent_bounce"
    assert attempt is not None
    assert attempt.status == "failed"


async def test_worker_rechecks_suppressions_before_provider_call(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await configure_provider(client, project["id"])
    await client.post("/api/v1/emails", json=email_payload(project["id"]))
    suppression = await client.post(
        f"/api/v1/projects/{project['id']}/suppressions",
        json={"email": "reader@example.net", "reason": "late complaint"},
    )
    assert suppression.status_code == 201
    message_id = (await claim_due_messages(app.state.session_factory, test_settings))[0]
    provider = FakeProvider()
    await process_message(app.state.session_factory, provider, test_settings, message_id)
    async with app.state.session_factory() as session:
        message = await session.get(EmailMessage, message_id)
        attempts = list(
            await session.scalars(
                select(DeliveryAttempt).where(DeliveryAttempt.message_id == message_id)
            )
        )
    assert message is not None
    assert message.status == "suppressed"
    assert message.suppressed_recipients == ["reader@example.net"]
    assert attempts == []
    assert provider.messages == []


async def test_worker_recovers_stale_lock_and_closes_attempt(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await configure_provider(client, project["id"])
    await client.post("/api/v1/emails", json=email_payload(project["id"]))
    message_id = (await claim_due_messages(app.state.session_factory, test_settings))[0]
    async with app.state.session_factory() as session, session.begin():
        message = await session.get(EmailMessage, message_id)
        assert message is not None
        message.attempt_count = 1
        message.locked_at = datetime.now(UTC) - timedelta(
            seconds=test_settings.worker_lock_timeout_seconds + 1
        )
        session.add(DeliveryAttempt(message_id=message_id, attempt_number=1, status="sending"))

    recovered = await claim_due_messages(app.state.session_factory, test_settings)
    assert recovered == [message_id]
    async with app.state.session_factory() as session:
        attempt = await session.scalar(
            select(DeliveryAttempt).where(DeliveryAttempt.message_id == message_id)
        )
    assert attempt is not None
    assert attempt.status == "failed"
    assert attempt.error_code == "worker_lock_expired"
    assert attempt.completed_at is not None


async def test_worker_uses_each_messages_project_credentials(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    configure_provider: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    first_project = await create_project(client, "First")
    second_project = await create_project(client, "Second")
    for project in (first_project, second_project):
        await add_verified_domain(client, project["id"])
    await configure_provider(
        client,
        first_project["id"],
        account_id="account-first",
        api_token="token-for-first-project-1234",
    )
    await configure_provider(
        client,
        second_project["id"],
        account_id="account-second",
        api_token="token-for-second-project-5678",
    )
    first_email = await client.post(
        "/api/v1/emails", json=email_payload(first_project["id"], subject="First")
    )
    second_email = await client.post(
        "/api/v1/emails", json=email_payload(second_project["id"], subject="Second")
    )
    assert first_email.status_code == 202
    assert second_email.status_code == 202

    provider = FakeProvider()
    claimed = await claim_due_messages(app.state.session_factory, test_settings)
    assert len(claimed) == 2
    for message_id in claimed:
        await process_message(app.state.session_factory, provider, test_settings, message_id)

    credentials_by_message = {
        message.message_id: credentials
        for message, credentials in zip(provider.messages, provider.credentials, strict=True)
    }
    first_credentials = credentials_by_message[first_email.json()["id"]]
    second_credentials = credentials_by_message[second_email.json()["id"]]
    assert (first_credentials.account_id, first_credentials.api_token) == (
        "account-first",
        "token-for-first-project-1234",
    )
    assert (second_credentials.account_id, second_credentials.api_token) == (
        "account-second",
        "token-for-second-project-5678",
    )


async def test_worker_fails_unconfigured_project_without_calling_provider(
    app: Any,
    client: httpx.AsyncClient,
    register_user: Any,
    create_project: Any,
    add_verified_domain: Any,
    test_settings: Settings,
) -> None:
    await register_user(client)
    project = await create_project(client)
    await add_verified_domain(client, project["id"])
    await client.post("/api/v1/emails", json=email_payload(project["id"]))
    message_id = (await claim_due_messages(app.state.session_factory, test_settings))[0]
    provider = FakeProvider()

    await process_message(app.state.session_factory, provider, test_settings, message_id)

    async with app.state.session_factory() as session:
        message = await session.get(EmailMessage, message_id)
    assert message is not None
    assert message.status == "failed"
    assert message.error_code == "provider_not_configured"
    assert provider.messages == []


async def test_cloudflare_adapter_preserves_result_and_classifies_all_bounces() -> None:
    requests: list[httpx.Request] = []

    async def accepted(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "message_id": "cf-1",
                    "delivered": [],
                    "queued": ["reader@example.net"],
                    "permanent_bounces": [],
                },
            },
        )

    settings = Settings(
        environment="test",
        session_secret="test-session-secret-with-at-least-32-characters",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(accepted))
    provider = CloudflareEmailProvider(settings, client)
    message = OutboundMessage(
        message_id="email-1",
        sender=_mailbox("hello@example.com"),
        to=[_mailbox("reader@example.net")],
        bcc=[_mailbox("audit@example.net")],
        subject="Hello",
        text="Hello",
    )
    result = await provider.send(
        message, ProviderCredentials(account_id="account-1", api_token="secret-token")
    )
    assert result.message_id == "cf-1"
    assert requests[0].url.path.endswith("/accounts/account-1/email/sending/send")
    assert requests[0].headers["authorization"] == "Bearer secret-token"
    assert b"audit@example.net" in requests[0].content
    await client.aclose()

    async def bounced(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "message_id": "cf-2",
                    "delivered": [],
                    "queued": [],
                    "permanent_bounces": ["reader@example.net"],
                },
            },
        )

    bounce_client = httpx.AsyncClient(transport=httpx.MockTransport(bounced))
    bounce_provider = CloudflareEmailProvider(settings, bounce_client)
    try:
        await bounce_provider.send(
            message, ProviderCredentials(account_id="account-1", api_token="secret-token")
        )
    except ProviderError as exc:
        assert exc.code == "provider_permanent_bounce"
        assert exc.retriable is False
    else:
        raise AssertionError("Expected permanent bounce failure")
    await bounce_client.aclose()


def _mailbox(email: str) -> Any:
    from app.providers.base import OutboundMailbox

    return OutboundMailbox(email=email)
