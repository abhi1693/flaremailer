from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import abort
from app.models import EmailMessage, EmailTemplate, SenderDomain, Suppression
from app.schemas import EmailCreate
from app.security import generate_public_email_id
from app.services.templates import render_template


async def enqueue_email(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    request: EmailCreate,
    settings: Settings,
    idempotency_key: str | None,
    resend_of_id: uuid.UUID | None = None,
) -> tuple[EmailMessage, bool]:
    fingerprint = _fingerprint(request)
    if idempotency_key:
        existing = await session.scalar(
            select(EmailMessage).where(
                EmailMessage.project_id == project_id,
                EmailMessage.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            _validate_fingerprint(existing, fingerprint)
            return existing, True

    sender_domain = str(request.sender.email).rsplit("@", 1)[1].lower()
    active_domains = list(
        await session.scalars(
            select(SenderDomain.domain).where(
                SenderDomain.project_id == project_id,
                SenderDomain.verified.is_(True),
                SenderDomain.active.is_(True),
            )
        )
    )
    if not any(
        sender_domain == domain or sender_domain.endswith(f".{domain}") for domain in active_domains
    ):
        abort(
            422,
            "sender_domain_not_verified",
            "The sender domain is not active and verified for this project",
        )

    template_id: uuid.UUID | None = None
    variables = request.variables
    if request.template_id is not None:
        template = await session.scalar(
            select(EmailTemplate).where(
                EmailTemplate.id == request.template_id,
                EmailTemplate.project_id == project_id,
            )
        )
        if template is None:
            abort(404, "template_not_found", "Template not found")
        rendered = render_template(
            template.subject, template.html_body, template.text_body, request.variables
        )
        subject, html, text = rendered.subject, rendered.html, rendered.text
        template_id = template.id
    else:
        assert request.subject is not None
        subject, html, text = request.subject, request.html, request.text

    recipient_addresses = {
        str(mailbox.email).lower() for mailbox in [*request.to, *request.cc, *request.bcc]
    }
    suppressed = list(
        await session.scalars(
            select(Suppression.email).where(
                Suppression.project_id == project_id,
                Suppression.email.in_(recipient_addresses),
            )
        )
    )
    now = datetime.now(UTC)
    message = EmailMessage(
        public_id=generate_public_email_id(),
        project_id=project_id,
        template_id=template_id,
        resend_of_id=resend_of_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint if idempotency_key else None,
        from_email=str(request.sender.email).lower(),
        from_name=request.sender.name,
        to_recipients=_mailboxes(request.to),
        cc_recipients=_mailboxes(request.cc),
        bcc_recipients=_mailboxes(request.bcc),
        reply_to=(request.reply_to.model_dump(mode="json") if request.reply_to else None),
        subject=subject,
        html_body=html,
        text_body=text,
        template_variables=variables,
        tags=request.tags,
        status="suppressed" if suppressed else "queued",
        suppressed_recipients=sorted(suppressed),
        max_attempts=settings.worker_max_attempts,
        next_attempt_at=None if suppressed else now,
        error_code="recipient_suppressed" if suppressed else None,
        error_message="One or more recipients are locally suppressed" if suppressed else None,
    )
    session.add(message)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if not idempotency_key:
            raise
        existing = await session.scalar(
            select(EmailMessage).where(
                EmailMessage.project_id == project_id,
                EmailMessage.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise
        _validate_fingerprint(existing, fingerprint)
        return existing, True
    await session.refresh(message)
    return message, False


def _mailboxes(mailboxes: list[Any]) -> list[dict[str, Any]]:
    return [mailbox.model_dump(mode="json") for mailbox in mailboxes]


def _fingerprint(request: EmailCreate) -> str:
    canonical = json.dumps(
        request.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_fingerprint(message: EmailMessage, fingerprint: str) -> None:
    if message.request_fingerprint != fingerprint:
        abort(
            409,
            "idempotency_conflict",
            "The idempotency key was already used with a different request",
        )
