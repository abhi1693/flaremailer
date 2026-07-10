from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, owned_project_or_404
from app.errors import abort
from app.models import Suppression, User
from app.schemas import SuppressionCreate, SuppressionListResponse, SuppressionResponse

router = APIRouter(prefix="/projects/{project_id}/suppressions", tags=["suppressions"])


@router.get("", response_model=SuppressionListResponse, operation_id="suppressionsList")
async def list_suppressions(
    project_id: uuid.UUID,
    search: str | None = Query(default=None, max_length=320),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuppressionListResponse:
    await owned_project_or_404(session, project_id, user.id)
    filters = [Suppression.project_id == project_id]
    if search:
        filters.append(func.lower(Suppression.email).like(f"%{search.lower()}%"))
    total = await session.scalar(select(func.count()).select_from(Suppression).where(*filters))
    items = list(
        await session.scalars(
            select(Suppression)
            .where(*filters)
            .order_by(Suppression.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return SuppressionListResponse(
        items=[SuppressionResponse.model_validate(item) for item in items], total=total or 0
    )


@router.post(
    "",
    response_model=SuppressionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="suppressionsCreate",
)
async def create_suppression(
    project_id: uuid.UUID,
    payload: SuppressionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuppressionResponse:
    await owned_project_or_404(session, project_id, user.id)
    suppression = Suppression(
        project_id=project_id, email=str(payload.email).lower(), reason=payload.reason
    )
    session.add(suppression)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        abort(409, "suppression_exists", "This email address is already suppressed")
    await session.refresh(suppression)
    return SuppressionResponse.model_validate(suppression)


@router.delete(
    "/{suppression_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="suppressionsDelete",
)
async def delete_suppression(
    project_id: uuid.UUID,
    suppression_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await owned_project_or_404(session, project_id, user.id)
    suppression = await session.scalar(
        select(Suppression).where(
            Suppression.id == suppression_id, Suppression.project_id == project_id
        )
    )
    if suppression is None:
        abort(404, "suppression_not_found", "Suppression not found")
    await session.delete(suppression)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
