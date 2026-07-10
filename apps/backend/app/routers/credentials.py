from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.credentials import CredentialCipher
from app.database import get_session
from app.dependencies import get_app_settings, get_current_user, owned_project_or_404
from app.errors import abort
from app.models import ProjectProviderCredentials, User
from app.schemas import ProjectCredentialsResponse, ProjectCredentialsWrite

router = APIRouter(prefix="/projects/{project_id}/credentials", tags=["project credentials"])


@router.get(
    "",
    response_model=ProjectCredentialsResponse,
    operation_id="projectCredentialsGet",
)
async def get_project_credentials(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectCredentialsResponse:
    await owned_project_or_404(session, project_id, user.id)
    credentials = await session.get(ProjectProviderCredentials, project_id)
    return _credential_response(credentials)


@router.put(
    "",
    response_model=ProjectCredentialsResponse,
    operation_id="projectCredentialsUpsert",
)
async def upsert_project_credentials(
    project_id: uuid.UUID,
    payload: ProjectCredentialsWrite,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> ProjectCredentialsResponse:
    await owned_project_or_404(session, project_id, user.id)
    credentials = await session.get(ProjectProviderCredentials, project_id)
    api_token = payload.api_token.get_secret_value() if payload.api_token is not None else None
    if credentials is None and api_token is None:
        abort(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "api_token_required",
            "api_token is required when credentials are configured for the first time",
        )

    if credentials is None:
        assert api_token is not None
        credentials = ProjectProviderCredentials(
            project_id=project_id,
            account_id=payload.account_id,
            api_token_encrypted=CredentialCipher(
                settings.credential_encryption_key, project_id
            ).encrypt(api_token),
            token_last_four=api_token[-4:],
        )
        session.add(credentials)
    else:
        credentials.account_id = payload.account_id
        if api_token is not None:
            credentials.api_token_encrypted = CredentialCipher(
                settings.credential_encryption_key, project_id
            ).encrypt(api_token)
            credentials.token_last_four = api_token[-4:]

    await session.commit()
    await session.refresh(credentials)
    return _credential_response(credentials)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="projectCredentialsDelete",
)
async def delete_project_credentials(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await owned_project_or_404(session, project_id, user.id)
    credentials = await session.get(ProjectProviderCredentials, project_id)
    if credentials is not None:
        await session.delete(credentials)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _credential_response(
    credentials: ProjectProviderCredentials | None,
) -> ProjectCredentialsResponse:
    if credentials is None:
        return ProjectCredentialsResponse(
            configured=False,
            account_id=None,
            token_last_four=None,
            updated_at=None,
        )
    return ProjectCredentialsResponse(
        configured=True,
        account_id=credentials.account_id,
        token_last_four=credentials.token_last_four,
        updated_at=credentials.updated_at,
    )
