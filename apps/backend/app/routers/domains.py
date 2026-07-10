from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, owned_project_or_404
from app.errors import abort
from app.models import SenderDomain, User
from app.schemas import DomainCreate, DomainListResponse, DomainResponse, DomainUpdate

router = APIRouter(prefix="/projects/{project_id}/domains", tags=["domains"])


@router.get("", response_model=DomainListResponse, operation_id="domainsList")
async def list_domains(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DomainListResponse:
    await owned_project_or_404(session, project_id, user.id)
    domains = list(
        await session.scalars(
            select(SenderDomain)
            .where(SenderDomain.project_id == project_id)
            .order_by(SenderDomain.created_at.desc())
        )
    )
    return DomainListResponse(items=[DomainResponse.model_validate(item) for item in domains])


@router.post(
    "",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="domainsCreate",
)
async def create_domain(
    project_id: uuid.UUID,
    payload: DomainCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DomainResponse:
    await owned_project_or_404(session, project_id, user.id)
    domain = SenderDomain(project_id=project_id, **payload.model_dump())
    session.add(domain)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        abort(409, "domain_already_exists", "This sender domain is already recorded")
    await session.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.patch("/{domain_id}", response_model=DomainResponse, operation_id="domainsUpdate")
async def update_domain(
    project_id: uuid.UUID,
    domain_id: uuid.UUID,
    payload: DomainUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DomainResponse:
    await owned_project_or_404(session, project_id, user.id)
    domain = await session.scalar(
        select(SenderDomain).where(
            SenderDomain.id == domain_id, SenderDomain.project_id == project_id
        )
    )
    if domain is None:
        abort(404, "domain_not_found", "Sender domain not found")
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(domain, name, value)
    await session.commit()
    await session.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.delete(
    "/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="domainsDelete",
)
async def delete_domain(
    project_id: uuid.UUID,
    domain_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await owned_project_or_404(session, project_id, user.id)
    domain = await session.scalar(
        select(SenderDomain).where(
            SenderDomain.id == domain_id, SenderDomain.project_id == project_id
        )
    )
    if domain is None:
        abort(404, "domain_not_found", "Sender domain not found")
    await session.delete(domain)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
