from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import validate_request_origin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, hash_session_token, new_session_token, verify_password
from app.models.user import User, UserSession
from app.schemas.auth import CredentialsRequest, UserResponse

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    dependencies=[Depends(validate_request_origin)],
)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.AUTH_SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


async def get_current_user(
    token: Optional[str] = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cần đăng nhập")

    now = datetime.now(timezone.utc)
    session_result = await db.execute(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn")

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn tồn tại")
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: CredentialsRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    password_hash = await run_in_threadpool(hash_password, payload.password)
    user = User(email=payload.email, password_hash=password_hash)
    token = new_session_token()
    now = datetime.now(timezone.utc)
    db.add(user)
    try:
        await db.flush()
        db.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_session_token(token),
                expires_at=now + timedelta(days=settings.AUTH_SESSION_TTL_DAYS),
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký",
        ) from exc

    await db.refresh(user)
    _set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: CredentialsRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    password_matches = False
    if user is not None:
        password_matches = await run_in_threadpool(verify_password, payload.password, user.password_hash)
    if not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    token = new_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.AUTH_SESSION_TTL_DAYS),
        )
    )
    await db.commit()
    _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token: Optional[str] = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if token:
        result = await db.execute(
            select(UserSession).where(UserSession.token_hash == hash_session_token(token))
        )
        session = result.scalar_one_or_none()
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            await db.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user
