from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, owned_project_or_404
from app.errors import abort
from app.models import ApiKey, User
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.security import generate_api_key

router = APIRouter(prefix="/projects/{project_id}/api-keys", tags=["api-keys"])


@router.get("", response_model=ApiKeyListResponse, operation_id="apiKeysList")
async def list_api_keys(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyListResponse:
    await owned_project_or_404(session, project_id, user.id)
    keys = list(
        await session.scalars(
            select(ApiKey).where(ApiKey.project_id == project_id).order_by(ApiKey.created_at.desc())
        )
    )
    return ApiKeyListResponse(items=[ApiKeyResponse.model_validate(item) for item in keys])


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="apiKeysCreate",
)
async def create_api_key(
    project_id: uuid.UUID,
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreatedResponse:
    await owned_project_or_404(session, project_id, user.id)
    plaintext, prefix, key_hash = generate_api_key()
    key = ApiKey(project_id=project_id, name=payload.name, prefix=prefix, key_hash=key_hash)
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(key).model_dump(), plaintext=plaintext
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="apiKeysRevoke",
)
async def revoke_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await owned_project_or_404(session, project_id, user.id)
    key = await session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id)
    )
    if key is None:
        abort(404, "api_key_not_found", "API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
