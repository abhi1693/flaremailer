from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.credentials import CredentialCipher, CredentialDecryptionError
from app.database import create_engine, create_session_factory
from app.models import DeliveryAttempt, EmailMessage, ProjectProviderCredentials, Suppression
from app.providers.base import (
    EmailProvider,
    OutboundMailbox,
    OutboundMessage,
    ProviderCredentials,
    ProviderError,
)
from app.providers.cloudflare import CloudflareEmailProvider

logger = logging.getLogger("flaremailer.worker")


async def claim_due_messages(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.worker_lock_timeout_seconds)
    claimed: list[uuid.UUID] = []
    async with session_factory() as session, session.begin():
        stale_message_ids = select(EmailMessage.id).where(
            EmailMessage.status == "sending",
            EmailMessage.locked_at < stale_before,
        )
        await session.execute(
            update(DeliveryAttempt)
            .where(
                DeliveryAttempt.message_id.in_(stale_message_ids),
                DeliveryAttempt.status == "sending",
            )
            .values(
                status="failed",
                error_code="worker_lock_expired",
                error_message="The worker lock expired before the attempt completed",
                completed_at=now,
            )
        )
        await session.execute(
            update(EmailMessage)
            .where(
                EmailMessage.status == "sending",
                EmailMessage.locked_at < stale_before,
            )
            .values(status="queued", locked_at=None, next_attempt_at=now)
        )
        query = (
            select(EmailMessage.id)
            .where(
                EmailMessage.status == "queued",
                or_(
                    EmailMessage.next_attempt_at.is_(None),
                    EmailMessage.next_attempt_at <= now,
                ),
            )
            .order_by(EmailMessage.created_at)
            .limit(settings.worker_batch_size)
        )
        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        candidates = list(await session.scalars(query))
        for message_id in candidates:
            result = await session.execute(
                update(EmailMessage)
                .where(EmailMessage.id == message_id, EmailMessage.status == "queued")
                .values(status="sending", locked_at=now)
            )
            if result.rowcount == 1:  # type: ignore[attr-defined]
                claimed.append(message_id)
    return claimed


async def release_claimed_messages(
    session_factory: async_sessionmaker[AsyncSession], message_ids: list[uuid.UUID]
) -> None:
    if not message_ids:
        return
    async with session_factory() as session, session.begin():
        await session.execute(
            update(EmailMessage)
            .where(
                EmailMessage.id.in_(message_ids),
                EmailMessage.status == "sending",
            )
            .values(status="queued", locked_at=None, next_attempt_at=datetime.now(UTC))
        )


async def process_message(
    session_factory: async_sessionmaker[AsyncSession],
    provider: EmailProvider,
    settings: Settings,
    message_id: uuid.UUID,
) -> None:
    async with session_factory() as session, session.begin():
        message = await session.get(EmailMessage, message_id)
        if message is None or message.status != "sending":
            return
        recipient_addresses = {
            str(item.get("email", "")).lower()
            for item in [
                *message.to_recipients,
                *message.cc_recipients,
                *message.bcc_recipients,
            ]
            if item.get("email")
        }
        suppressed = list(
            await session.scalars(
                select(Suppression.email).where(
                    Suppression.project_id == message.project_id,
                    Suppression.email.in_(recipient_addresses),
                )
            )
        )
        if suppressed:
            message.status = "suppressed"
            message.suppressed_recipients = sorted(suppressed)
            message.error_code = "recipient_suppressed"
            message.error_message = "One or more recipients are locally suppressed"
            message.locked_at = None
            message.next_attempt_at = None
            return
        message.attempt_count += 1
        attempt_number = message.attempt_count
        delivery_attempt = DeliveryAttempt(
            message_id=message.id,
            attempt_number=attempt_number,
            status="sending",
        )
        session.add(delivery_attempt)
        await session.flush()
        outbound = _outbound_message(message)
        stored_credentials = await session.get(ProjectProviderCredentials, message.project_id)
        attempt_id = delivery_attempt.id

    try:
        credentials = _resolve_provider_credentials(stored_credentials, settings)
        result = await provider.send(outbound, credentials)
    except ProviderError as exc:
        await _record_failure(
            session_factory,
            settings,
            message_id,
            attempt_id,
            code=exc.code,
            message=str(exc),
            raw_response=exc.raw_response,
            retriable=exc.retriable,
        )
        return
    except Exception as exc:
        logger.exception("Unexpected provider failure", extra={"message_id": str(message_id)})
        await _record_failure(
            session_factory,
            settings,
            message_id,
            attempt_id,
            code="worker_unexpected_error",
            message=str(exc)[:2000],
            raw_response=None,
            retriable=True,
        )
        return

    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        message = await session.get(EmailMessage, message_id)
        stored_attempt = await session.get(DeliveryAttempt, attempt_id)
        if message is None or stored_attempt is None:
            return
        message.status = "sent"
        message.provider_message_id = result.message_id
        message.provider_response = result.raw_response
        message.error_code = None
        message.error_message = None
        message.locked_at = None
        message.next_attempt_at = None
        message.sent_at = now
        stored_attempt.status = "sent"
        stored_attempt.provider_response = result.raw_response
        stored_attempt.completed_at = now
    logger.info(
        "Email accepted by Cloudflare",
        extra={"message_id": str(message_id), "provider_message_id": result.message_id},
    )


async def _record_failure(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    message_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    code: str,
    message: str,
    raw_response: dict[str, Any] | None,
    retriable: bool,
) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        email = await session.get(EmailMessage, message_id)
        attempt = await session.get(DeliveryAttempt, attempt_id)
        if email is None or attempt is None:
            return
        should_retry = retriable and email.attempt_count < email.max_attempts
        email.status = "queued" if should_retry else "failed"
        email.error_code = code
        email.error_message = message[:4000]
        email.provider_response = raw_response
        email.locked_at = None
        email.next_attempt_at = (
            now + timedelta(seconds=_backoff_seconds(settings, email.attempt_count))
            if should_retry
            else None
        )
        attempt.status = "failed"
        attempt.error_code = code
        attempt.error_message = message[:4000]
        attempt.provider_response = raw_response
        attempt.completed_at = now
    logger.warning(
        "Email provider attempt failed",
        extra={
            "message_id": str(message_id),
            "code": code,
            "will_retry": should_retry,
        },
    )


def _outbound_message(message: EmailMessage) -> OutboundMessage:
    return OutboundMessage(
        message_id=message.public_id,
        sender=OutboundMailbox(message.from_email, message.from_name),
        to=[_outbound_mailbox(item) for item in message.to_recipients],
        cc=[_outbound_mailbox(item) for item in message.cc_recipients],
        bcc=[_outbound_mailbox(item) for item in message.bcc_recipients],
        reply_to=_outbound_mailbox(message.reply_to) if message.reply_to else None,
        subject=message.subject,
        html=message.html_body,
        text=message.text_body,
    )


def _resolve_provider_credentials(
    stored: ProjectProviderCredentials | None, settings: Settings
) -> ProviderCredentials:
    if stored is None:
        raise ProviderError(
            "Cloudflare Email Service credentials are not configured for this project",
            code="provider_not_configured",
            retriable=False,
        )
    try:
        api_token = CredentialCipher(settings.credential_encryption_key, stored.project_id).decrypt(
            stored.api_token_encrypted
        )
    except CredentialDecryptionError as exc:
        raise ProviderError(
            "The project's Cloudflare credentials could not be decrypted",
            code="provider_credentials_invalid",
            retriable=False,
        ) from exc
    return ProviderCredentials(account_id=stored.account_id, api_token=api_token)


def _outbound_mailbox(value: dict[str, object]) -> OutboundMailbox:
    email = value.get("email")
    name = value.get("name")
    if not isinstance(email, str):
        raise ValueError("Stored recipient is invalid")
    return OutboundMailbox(email=email, name=name if isinstance(name, str) else None)


def _backoff_seconds(settings: Settings, attempt_count: int) -> int:
    schedule = settings.worker_backoff_schedule
    return schedule[min(max(attempt_count - 1, 0), len(schedule) - 1)]


async def run_worker(*, once: bool = False, settings: Settings | None = None) -> None:
    app_settings = settings or get_settings()
    engine = create_engine(app_settings)
    session_factory = create_session_factory(engine)
    provider = CloudflareEmailProvider(app_settings)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            pass
    try:
        while not stop_event.is_set():
            message_ids = await claim_due_messages(session_factory, app_settings)
            for index, message_id in enumerate(message_ids):
                if stop_event.is_set():
                    await release_claimed_messages(session_factory, message_ids[index:])
                    break
                await process_message(session_factory, provider, app_settings, message_id)
            if once:
                break
            if not message_ids:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=app_settings.worker_poll_seconds
                    )
                except TimeoutError:
                    pass
    finally:
        await provider.aclose()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Flaremailer durable email delivery worker")
    parser.add_argument("--once", action="store_true", help="Process one available batch and exit")
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker(once=args.once, settings=settings))


if __name__ == "__main__":
    main()
