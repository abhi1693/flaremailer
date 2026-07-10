from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DomainName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=253)]
EmailStatus = Literal["queued", "sending", "sent", "failed", "suppressed"]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserResponse(ApiModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class AuthResponse(ApiModel):
    user: UserResponse


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ProjectCreate(ApiModel):
    name: Name


class ProjectUpdate(ApiModel):
    name: Name


class ProjectResponse(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(ApiModel):
    items: list[ProjectResponse]


class ProjectCredentialsWrite(ApiModel):
    account_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    api_token: SecretStr | None = Field(default=None, min_length=16, max_length=2048)

    @field_validator("api_token", mode="before")
    @classmethod
    def validate_api_token(cls, value: object) -> object:
        if value is None:
            return None
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str):
            raise ValueError("api_token must be a string")
        normalized = raw_value.strip()
        if len(normalized) < 16:
            raise ValueError("api_token must contain at least 16 characters")
        if len(normalized) > 2048:
            raise ValueError("api_token cannot exceed 2048 characters")
        return SecretStr(normalized)


class ProjectCredentialsResponse(ApiModel):
    configured: bool
    account_id: str | None
    token_last_four: str | None
    updated_at: datetime | None


class ApiKeyCreate(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ApiKeyResponse(ApiModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreatedResponse(ApiKeyResponse):
    plaintext: str = Field(
        description="The complete API key. It is returned once and cannot be recovered."
    )


class ApiKeyListResponse(ApiModel):
    items: list[ApiKeyResponse]


class DomainCreate(ApiModel):
    domain: DomainName
    verified: bool = False
    active: bool = True

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = value.rstrip(".").lower()
        try:
            encoded = domain.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid domain") from exc
        labels = encoded.split(".")
        if len(labels) < 2 or any(not label or len(label) > 63 for label in labels):
            raise ValueError("Enter a fully-qualified domain")
        return encoded


class DomainUpdate(ApiModel):
    verified: bool | None = None
    active: bool | None = None


class DomainResponse(ApiModel):
    id: uuid.UUID
    domain: str
    verified: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class DomainListResponse(ApiModel):
    items: list[DomainResponse]


class TemplateCreate(ApiModel):
    name: Name
    slug: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ] = None
    subject: Annotated[str, StringConstraints(min_length=1, max_length=998)]
    html: Annotated[str | None, StringConstraints(max_length=2_000_000)] = None
    text: Annotated[str | None, StringConstraints(max_length=1_000_000)] = None

    @model_validator(mode="after")
    def require_content(self) -> TemplateCreate:
        if self.html is None and self.text is None:
            raise ValueError("At least one of html or text is required")
        _reject_header_newlines(self.subject, "subject")
        return self


class TemplateUpdate(ApiModel):
    name: Name | None = None
    subject: Annotated[str | None, StringConstraints(min_length=1, max_length=998)] = None
    html: Annotated[str | None, StringConstraints(max_length=2_000_000)] = None
    text: Annotated[str | None, StringConstraints(max_length=1_000_000)] = None

    @field_validator("subject")
    @classmethod
    def safe_subject(cls, value: str | None) -> str | None:
        if value is not None:
            _reject_header_newlines(value, "subject")
        return value

    @model_validator(mode="after")
    def require_non_null_identity_fields(self) -> TemplateUpdate:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "subject" in self.model_fields_set and self.subject is None:
            raise ValueError("subject cannot be null")
        return self


class TemplateResponse(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    subject: str
    html: str | None
    text: str | None
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(ApiModel):
    items: list[TemplateResponse]


class TemplatePreviewRequest(ApiModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class TemplatePreviewResponse(ApiModel):
    subject: str
    html: str | None
    text: str | None


class SuppressionCreate(ApiModel):
    email: EmailStr
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ] = "manual"


class SuppressionResponse(ApiModel):
    id: uuid.UUID
    email: EmailStr
    reason: str
    created_at: datetime


class SuppressionListResponse(ApiModel):
    items: list[SuppressionResponse]
    total: int


class Mailbox(ApiModel):
    email: EmailStr
    name: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=200)] = None

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str | None) -> str | None:
        if value is not None:
            _reject_header_newlines(value, "name")
        return value


class EmailCreate(ApiModel):
    project_id: uuid.UUID | None = Field(
        default=None,
        description="Required with session authentication; inferred from an API key.",
    )
    sender: Mailbox = Field(alias="from")
    to: list[Mailbox] = Field(min_length=1, max_length=50)
    cc: list[Mailbox] = Field(default_factory=list, max_length=50)
    bcc: list[Mailbox] = Field(default_factory=list, max_length=50)
    reply_to: Mailbox | None = None
    subject: Annotated[str | None, StringConstraints(min_length=1, max_length=998)] = None
    html: Annotated[str | None, StringConstraints(max_length=2_000_000)] = None
    text: Annotated[str | None, StringConstraints(max_length=1_000_000)] = None
    template_id: uuid.UUID | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    tags: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    ] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_message(self) -> EmailCreate:
        if len(self.to) + len(self.cc) + len(self.bcc) > 50:
            raise ValueError("Cloudflare allows at most 50 combined recipients")
        if self.template_id is None:
            if self.subject is None:
                raise ValueError("subject is required when template_id is not provided")
            if self.html is None and self.text is None:
                raise ValueError("At least one of html or text is required")
        elif any(value is not None for value in (self.subject, self.html, self.text)):
            raise ValueError("subject, html, and text cannot be supplied with template_id")
        if self.subject is not None:
            _reject_header_newlines(self.subject, "subject")
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("tags must be unique")
        return self


class EmailEnqueueResponse(ApiModel):
    id: str
    status: EmailStatus
    deduplicated: bool = False
    suppressed_recipients: list[EmailStr] = Field(default_factory=list)
    created_at: datetime


class DeliveryAttemptResponse(ApiModel):
    attempt_number: int
    status: str
    error_code: str | None
    error_message: str | None
    provider_response: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None


class EmailSummaryResponse(ApiModel):
    id: str
    project_id: uuid.UUID
    from_email: EmailStr
    to: list[Mailbox]
    subject: str
    status: EmailStatus
    tags: list[str]
    attempt_count: int
    provider_message_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None


class EmailDetailResponse(EmailSummaryResponse):
    cc: list[Mailbox]
    bcc: list[Mailbox]
    reply_to: Mailbox | None
    html: str | None
    text: str | None
    template_id: uuid.UUID | None
    variables: dict[str, Any]
    suppressed_recipients: list[EmailStr]
    provider_response: dict[str, Any] | None
    error_code: str | None
    resend_of_id: str | None
    attempts: list[DeliveryAttemptResponse]


class EmailListResponse(ApiModel):
    items: list[EmailSummaryResponse]
    total: int
    limit: int
    offset: int


class MetricsResponse(ApiModel):
    total: int
    queued: int
    sending: int
    sent: int
    failed: int
    suppressed: int
    sent_last_24_hours: int


class HealthResponse(ApiModel):
    status: Literal["ok"]


def _reject_header_newlines(value: str, field_name: str) -> None:
    if "\r" in value or "\n" in value:
        raise ValueError(f"{field_name} cannot contain line breaks")
