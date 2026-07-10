from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_session
from app.errors import abort
from app.models import ApiKey, Project, User
from app.security import hash_api_key, read_session_token


@dataclass(frozen=True, slots=True)
class EmailPrincipal:
    kind: Literal["session", "api_key"]
    project_id: uuid.UUID | None
    user_id: uuid.UUID | None
    api_key_id: uuid.UUID | None = None


def get_app_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are unavailable")
    return settings


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        abort(401, "authentication_required", "Sign in to continue")
    raw_user_id = read_session_token(token, settings)
    if not raw_user_id:
        abort(401, "invalid_session", "The session is invalid or expired")
    try:
        user_id = uuid.UUID(raw_user_id)
    except ValueError:
        abort(401, "invalid_session", "The session is invalid or expired")
    user = await session.get(User, user_id)
    if user is None:
        abort(401, "invalid_session", "The session is invalid or expired")
    return user


async def get_email_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> EmailPrincipal:
    authorization = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x-api-key")
    plaintext: str | None = x_api_key
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != "bearer" or not credentials:
            abort(401, "invalid_authorization", "Use a Bearer API key")
        plaintext = credentials

    if plaintext:
        if not plaintext.startswith("fm_live_") or len(plaintext) < 24:
            abort(401, "invalid_api_key", "The API key is invalid")
        prefix = plaintext[:20]
        key = await session.scalar(
            select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.revoked_at.is_(None))
        )
        if key is None or not hmac.compare_digest(key.key_hash, hash_api_key(plaintext)):
            abort(401, "invalid_api_key", "The API key is invalid")
        key.last_used_at = datetime.now(UTC)
        key.last_used_ip = request.client.host if request.client else None
        key.last_used_user_agent = request.headers.get("user-agent", "")[:255] or None
        await session.commit()
        return EmailPrincipal(
            kind="api_key", project_id=key.project_id, user_id=None, api_key_id=key.id
        )

    user = await get_current_user(request, session)
    return EmailPrincipal(kind="session", project_id=None, user_id=user.id)


async def owned_project_or_404(
    session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id)
    )
    if project is None:
        abort(404, "project_not_found", "Project not found")
    return project


async def resolve_principal_project(
    session: AsyncSession,
    principal: EmailPrincipal,
    requested_project_id: uuid.UUID | None,
) -> Project:
    if principal.kind == "api_key":
        if requested_project_id is not None and requested_project_id != principal.project_id:
            abort(403, "project_mismatch", "The API key does not belong to this project")
        project = await session.get(Project, principal.project_id)
        if project is None:
            abort(401, "invalid_api_key", "The API key project no longer exists")
        return project
    if requested_project_id is None:
        abort(422, "project_required", "project_id is required for session authentication")
    assert principal.user_id is not None
    return await owned_project_or_404(session, requested_project_id, principal.user_id)
