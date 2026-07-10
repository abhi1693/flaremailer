from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import get_session
from app.dependencies import (
    EmailPrincipal,
    get_email_principal,
    resolve_principal_project,
)
from app.errors import abort
from app.models import DeliveryAttempt, EmailMessage
from app.schemas import (
    DeliveryAttemptResponse,
    EmailCreate,
    EmailDetailResponse,
    EmailEnqueueResponse,
    EmailListResponse,
    EmailStatus,
    EmailSummaryResponse,
    Mailbox,
    MetricsResponse,
)
from app.services.emails import enqueue_email

router = APIRouter(prefix="/emails", tags=["emails"])
metrics_router = APIRouter(tags=["metrics"])


@router.post(
    "",
    response_model=EmailEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="emailsEnqueue",
)
async def create_email(
    payload: EmailCreate,
    request: Request,
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=255
    ),
    principal: EmailPrincipal = Depends(get_email_principal),
    session: AsyncSession = Depends(get_session),
) -> EmailEnqueueResponse:
    project = await resolve_principal_project(session, principal, payload.project_id)
    key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key and not key:
        abort(422, "invalid_idempotency_key", "Idempotency-Key cannot be blank")
    settings: Settings = request.app.state.settings
    message, deduplicated = await enqueue_email(
        session,
        project_id=project.id,
        request=payload,
        settings=settings,
        idempotency_key=key,
    )
    return _enqueue_response(message, deduplicated)


@router.get("", response_model=EmailListResponse, operation_id="emailsList")
async def list_emails(
    project_id: uuid.UUID | None = Query(default=None),
    email_status: EmailStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: EmailPrincipal = Depends(get_email_principal),
    session: AsyncSession = Depends(get_session),
) -> EmailListResponse:
    project = await resolve_principal_project(session, principal, project_id)
    filters = [EmailMessage.project_id == project.id]
    if email_status:
        filters.append(EmailMessage.status == email_status)
    if search:
        term = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(EmailMessage.public_id).like(term),
                func.lower(EmailMessage.subject).like(term),
                func.lower(EmailMessage.from_email).like(term),
                func.lower(EmailMessage.provider_message_id).like(term),
                func.lower(cast(EmailMessage.to_recipients, Text)).like(term),
                func.lower(cast(EmailMessage.cc_recipients, Text)).like(term),
                func.lower(cast(EmailMessage.bcc_recipients, Text)).like(term),
            )
        )
    total = await session.scalar(select(func.count()).select_from(EmailMessage).where(*filters))
    messages = list(
        await session.scalars(
            select(EmailMessage)
            .where(*filters)
            .order_by(EmailMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return EmailListResponse(
        items=[_summary_response(message) for message in messages],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{email_id}", response_model=EmailDetailResponse, operation_id="emailsGet")
async def get_email(
    email_id: str,
    project_id: uuid.UUID | None = Query(default=None),
    principal: EmailPrincipal = Depends(get_email_principal),
    session: AsyncSession = Depends(get_session),
) -> EmailDetailResponse:
    project = await resolve_principal_project(session, principal, project_id)
    message = await _message_or_404(session, project.id, email_id)
    return await _detail_response(session, message)


@router.post(
    "/{email_id}/resend",
    response_model=EmailEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="emailsResend",
)
async def resend_email(
    email_id: str,
    request: Request,
    project_id: uuid.UUID | None = Query(default=None),
    principal: EmailPrincipal = Depends(get_email_principal),
    session: AsyncSession = Depends(get_session),
) -> EmailEnqueueResponse:
    project = await resolve_principal_project(session, principal, project_id)
    original = await _message_or_404(session, project.id, email_id)
    if original.status in {"queued", "sending"}:
        abort(409, "email_still_in_progress", "Queued or sending email cannot be resent")
    payload = EmailCreate(
        project_id=project.id,
        **{
            "from": Mailbox(email=original.from_email, name=original.from_name),
            "to": [Mailbox.model_validate(item) for item in original.to_recipients],
            "cc": [Mailbox.model_validate(item) for item in original.cc_recipients],
            "bcc": [Mailbox.model_validate(item) for item in original.bcc_recipients],
            "reply_to": (Mailbox.model_validate(original.reply_to) if original.reply_to else None),
            "subject": original.subject,
            "html": original.html_body,
            "text": original.text_body,
            "tags": original.tags,
        },
    )
    settings: Settings = request.app.state.settings
    message, _ = await enqueue_email(
        session,
        project_id=project.id,
        request=payload,
        settings=settings,
        idempotency_key=None,
        resend_of_id=original.id,
    )
    return _enqueue_response(message, False)


@metrics_router.get("/metrics", response_model=MetricsResponse, operation_id="metricsGet")
async def get_metrics(
    project_id: uuid.UUID | None = Query(default=None),
    principal: EmailPrincipal = Depends(get_email_principal),
    session: AsyncSession = Depends(get_session),
) -> MetricsResponse:
    project = await resolve_principal_project(session, principal, project_id)
    rows = (
        await session.execute(
            select(EmailMessage.status, func.count(EmailMessage.id))
            .where(EmailMessage.project_id == project.id)
            .group_by(EmailMessage.status)
        )
    ).all()
    counts = {status_name: count for status_name, count in rows}
    sent_last_day = await session.scalar(
        select(func.count())
        .select_from(EmailMessage)
        .where(
            EmailMessage.project_id == project.id,
            EmailMessage.status == "sent",
            EmailMessage.sent_at >= datetime.now(UTC) - timedelta(hours=24),
        )
    )
    return MetricsResponse(
        total=sum(counts.values()),
        queued=counts.get("queued", 0),
        sending=counts.get("sending", 0),
        sent=counts.get("sent", 0),
        failed=counts.get("failed", 0),
        suppressed=counts.get("suppressed", 0),
        sent_last_24_hours=sent_last_day or 0,
    )


async def _message_or_404(
    session: AsyncSession, project_id: uuid.UUID, email_id: str
) -> EmailMessage:
    message = await session.scalar(
        select(EmailMessage)
        .options(selectinload(EmailMessage.attempts))
        .where(EmailMessage.public_id == email_id, EmailMessage.project_id == project_id)
    )
    if message is None:
        abort(404, "email_not_found", "Email not found")
    return message


def _enqueue_response(message: EmailMessage, deduplicated: bool) -> EmailEnqueueResponse:
    return EmailEnqueueResponse(
        id=message.public_id,
        status=message.status,
        deduplicated=deduplicated,
        suppressed_recipients=message.suppressed_recipients,
        created_at=message.created_at,
    )


def _summary_response(message: EmailMessage) -> EmailSummaryResponse:
    return EmailSummaryResponse(
        id=message.public_id,
        project_id=message.project_id,
        from_email=message.from_email,
        to=[Mailbox.model_validate(item) for item in message.to_recipients],
        subject=message.subject,
        status=message.status,
        tags=message.tags,
        attempt_count=message.attempt_count,
        provider_message_id=message.provider_message_id,
        error_message=message.error_message,
        created_at=message.created_at,
        updated_at=message.updated_at,
        sent_at=message.sent_at,
    )


async def _detail_response(session: AsyncSession, message: EmailMessage) -> EmailDetailResponse:
    resend_of_id: str | None = None
    if message.resend_of_id:
        resend_of_id = await session.scalar(
            select(EmailMessage.public_id).where(EmailMessage.id == message.resend_of_id)
        )
    return EmailDetailResponse(
        **_summary_response(message).model_dump(),
        cc=[Mailbox.model_validate(item) for item in message.cc_recipients],
        bcc=[Mailbox.model_validate(item) for item in message.bcc_recipients],
        reply_to=Mailbox.model_validate(message.reply_to) if message.reply_to else None,
        html=message.html_body,
        text=message.text_body,
        template_id=message.template_id,
        variables=message.template_variables,
        suppressed_recipients=message.suppressed_recipients,
        provider_response=message.provider_response,
        error_code=message.error_code,
        resend_of_id=resend_of_id,
        attempts=[_attempt_response(attempt) for attempt in message.attempts],
    )


def _attempt_response(attempt: DeliveryAttempt) -> DeliveryAttemptResponse:
    return DeliveryAttemptResponse.model_validate(attempt)
