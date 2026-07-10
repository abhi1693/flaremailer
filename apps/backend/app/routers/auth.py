from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_session
from app.dependencies import get_current_user
from app.errors import abort
from app.models import User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.security import hash_password, make_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="authRegister",
)
async def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    email = str(payload.email).lower()
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        abort(409, "email_already_registered", "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        abort(409, "email_already_registered", "An account with this email already exists")
    await session.refresh(user)
    _set_session_cookie(response, user, request.app.state.settings)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse, operation_id="authLogin")
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        abort(401, "invalid_credentials", "Email or password is incorrect")
    _set_session_cookie(response, user, request.app.state.settings)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="authLogout",
)
async def logout(request: Request, response: Response) -> Response:
    settings: Settings = request.app.state.settings
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthResponse, operation_id="authGetCurrentUser")
async def get_me(user: User = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=UserResponse.model_validate(user))


def _set_session_cookie(response: Response, user: User, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        make_session_token(str(user.id), settings),
        max_age=settings.session_max_age_seconds,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
