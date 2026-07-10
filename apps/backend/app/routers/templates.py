from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, owned_project_or_404
from app.errors import abort
from app.models import EmailTemplate, User
from app.schemas import (
    TemplateCreate,
    TemplateListResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.security import slugify
from app.services.templates import render_template, validate_template

router = APIRouter(prefix="/projects/{project_id}/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse, operation_id="templatesList")
async def list_templates(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateListResponse:
    await owned_project_or_404(session, project_id, user.id)
    templates = list(
        await session.scalars(
            select(EmailTemplate)
            .where(EmailTemplate.project_id == project_id)
            .order_by(EmailTemplate.created_at.desc())
        )
    )
    return TemplateListResponse(items=[_response(item) for item in templates])


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="templatesCreate",
)
async def create_template(
    project_id: uuid.UUID,
    payload: TemplateCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateResponse:
    await owned_project_or_404(session, project_id, user.id)
    validate_template(payload.subject, payload.html, payload.text)
    template = EmailTemplate(
        project_id=project_id,
        name=payload.name,
        slug=slugify(payload.slug or payload.name, fallback="template"),
        subject=payload.subject,
        html_body=payload.html,
        text_body=payload.text,
    )
    session.add(template)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        abort(409, "template_slug_exists", "A template with this slug already exists")
    await session.refresh(template)
    return _response(template)


@router.get("/{template_id}", response_model=TemplateResponse, operation_id="templatesGet")
async def get_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateResponse:
    await owned_project_or_404(session, project_id, user.id)
    return _response(await _template_or_404(session, project_id, template_id))


@router.patch("/{template_id}", response_model=TemplateResponse, operation_id="templatesUpdate")
async def update_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplateResponse:
    await owned_project_or_404(session, project_id, user.id)
    template = await _template_or_404(session, project_id, template_id)
    data = payload.model_dump(exclude_unset=True)
    name = data.get("name", template.name)
    subject = data.get("subject", template.subject)
    html = data.get("html", template.html_body)
    text = data.get("text", template.text_body)
    if html is None and text is None:
        abort(422, "template_content_required", "At least one of html or text is required")
    validate_template(subject, html, text)
    template.name = name
    template.subject = subject
    template.html_body = html
    template.text_body = text
    await session.commit()
    await session.refresh(template)
    return _response(template)


@router.post(
    "/{template_id}/preview",
    response_model=TemplatePreviewResponse,
    operation_id="templatesPreview",
)
async def preview_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: TemplatePreviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TemplatePreviewResponse:
    await owned_project_or_404(session, project_id, user.id)
    template = await _template_or_404(session, project_id, template_id)
    rendered = render_template(
        template.subject, template.html_body, template.text_body, payload.variables
    )
    return TemplatePreviewResponse(subject=rendered.subject, html=rendered.html, text=rendered.text)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="templatesDelete",
)
async def delete_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await owned_project_or_404(session, project_id, user.id)
    template = await _template_or_404(session, project_id, template_id)
    await session.delete(template)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _template_or_404(
    session: AsyncSession, project_id: uuid.UUID, template_id: uuid.UUID
) -> EmailTemplate:
    template = await session.scalar(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id, EmailTemplate.project_id == project_id
        )
    )
    if template is None:
        abort(404, "template_not_found", "Template not found")
    return template


def _response(template: EmailTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        name=template.name,
        slug=template.slug,
        subject=template.subject,
        html=template.html_body,
        text=template.text_body,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )
