from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, owned_project_or_404
from app.models import Project, User
from app.schemas import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.security import slugify

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse, operation_id="projectsList")
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    projects = list(
        await session.scalars(
            select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())
        )
    )
    return ProjectListResponse(items=[ProjectResponse.model_validate(item) for item in projects])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="projectsCreate",
)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    base_slug = slugify(payload.name)
    slug = base_slug
    counter = 2
    while await session.scalar(
        select(Project.id).where(Project.owner_id == user.id, Project.slug == slug)
    ):
        suffix = f"-{counter}"
        slug = f"{base_slug[: 64 - len(suffix)]}{suffix}"
        counter += 1
    project = Project(owner_id=user.id, name=payload.name, slug=slug)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse, operation_id="projectsGet")
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await owned_project_or_404(session, project_id, user.id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, operation_id="projectsUpdate")
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await owned_project_or_404(session, project_id, user.id)
    project.name = payload.name
    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="projectsDelete",
)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    project = await owned_project_or_404(session, project_id, user.id)
    await session.delete(project)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
