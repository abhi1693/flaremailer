from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_projects_owner_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)

    owner: Mapped[User] = relationship(back_populates="projects")
    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    domains: Mapped[list[SenderDomain]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    templates: Mapped[list[EmailTemplate]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    suppressions: Mapped[list[Suppression]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    emails: Mapped[list[EmailMessage]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    provider_credentials: Mapped[ProjectProviderCredentials | None] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class ProjectProviderCredentials(TimestampMixin, Base):
    __tablename__ = "project_provider_credentials"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    api_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_last_four: Mapped[str] = mapped_column(String(4), nullable=False)

    project: Mapped[Project] = relationship(back_populates="provider_credentials")


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[str | None] = mapped_column(String(64))
    last_used_user_agent: Mapped[str | None] = mapped_column(String(255))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    project: Mapped[Project] = relationship(back_populates="api_keys")


class SenderDomain(TimestampMixin, Base):
    __tablename__ = "sender_domains"
    __table_args__ = (
        UniqueConstraint("project_id", "domain", name="uq_sender_domains_project_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped[Project] = relationship(back_populates="domains")


class EmailTemplate(TimestampMixin, Base):
    __tablename__ = "email_templates"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_email_templates_project_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="templates")
    emails: Mapped[list[EmailMessage]] = relationship(back_populates="template")


class Suppression(Base):
    __tablename__ = "suppressions"
    __table_args__ = (
        UniqueConstraint("project_id", "email", name="uq_suppressions_project_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="suppressions")


class EmailMessage(TimestampMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_email_messages_project_idempotency"
        ),
        CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed', 'suppressed')",
            name="ck_email_messages_status",
        ),
        Index("ix_email_messages_project_created", "project_id", "created_at"),
        Index("ix_email_messages_worker", "status", "next_attempt_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_templates.id", ondelete="SET NULL"), index=True
    )
    resend_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_messages.id", ondelete="SET NULL"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))

    from_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(200))
    to_recipients: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    cc_recipients: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    bcc_recipients: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    reply_to: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text)
    template_variables: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False, index=True)
    suppressed_recipients: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="emails")
    template: Mapped[EmailTemplate | None] = relationship(back_populates="emails")
    attempts: Mapped[list[DeliveryAttempt]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DeliveryAttempt.attempt_number",
    )
    resend_of: Mapped[EmailMessage | None] = relationship(remote_side=[id])


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        UniqueConstraint("message_id", "attempt_number", name="uq_delivery_attempt_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    message: Mapped[EmailMessage] = relationship(back_populates="attempts")
