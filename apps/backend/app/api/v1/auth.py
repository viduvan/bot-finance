"""Authentication API: login, refresh, logout, 2FA setup/verify."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_provisioning_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from app.database.session import get_db_session
from app.models.user import User

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    mfa_code: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    mfa_enabled: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    role: str = "TRADER"


# ── Dependencies ─────────────────────────────────────────────────


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Placeholder dependency - will be enhanced with JWT middleware."""
    # This is a simplified version for Phase 0
    # Full JWT middleware will be added as a proper dependency
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """Authenticate user and return JWT tokens.

    If MFA is enabled, requires valid TOTP code.
    """
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        logger.warning("login_failed", email=request.email, reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        logger.warning("login_failed", email=request.email, reason="account_disabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Check MFA
    if user.mfa_enabled:
        if not request.mfa_code:
            return LoginResponse(
                access_token="",
                refresh_token="",
                mfa_required=True,
            )
        if not user.mfa_secret or not verify_totp(user.mfa_secret, request.mfa_code):
            logger.warning("login_failed", email=request.email, reason="invalid_mfa")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

    # Generate tokens
    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))

    logger.info("user_logged_in", user_id=str(user.id), email=user.email)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """Refresh access token using a valid refresh token."""
    payload = decode_token(request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    access_token = create_access_token(str(user.id), user.role)
    new_refresh_token = create_refresh_token(str(user.id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout() -> dict:
    """Logout user (client should discard tokens)."""
    # In a production system, we'd add the token to a Redis blacklist
    return {"message": "Successfully logged out"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    """Register a new user (for initial setup)."""
    # Check if user exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        is_active=True,
        mfa_enabled=False,
    )
    db.add(user)
    await db.flush()

    logger.info("user_registered", user_id=str(user.id), email=user.email, role=user.role)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MFASetupResponse:
    """Generate TOTP secret and provisioning URI for 2FA setup.

    User should scan the QR code with an authenticator app,
    then verify with /mfa/verify to activate.
    """
    # TODO: Require authenticated user (will be added with JWT middleware)
    secret = generate_totp_secret()
    uri = get_totp_provisioning_uri(secret, "admin@acta.local")

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=uri,
    )
