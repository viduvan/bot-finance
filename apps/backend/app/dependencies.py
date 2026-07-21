"""FastAPI dependency injection container.

Provides database sessions, authenticated users, and permission checks
as injectable dependencies for API routes.
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import Permission, ROLE_PERMISSIONS, UserRole
from app.core.exceptions import AuthenticationError, AuthorizationError, TokenExpiredError
from app.core.security import decode_token
from app.database.session import get_db_session
from app.models.user import User

logger = structlog.get_logger(__name__)


# ── Database Session ─────────────────────────────────────────────

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# ── JWT Authentication ───────────────────────────────────────────


async def get_current_user(
    db: DBSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Extract and validate JWT token, return authenticated user.

    Usage:
        @router.get("/protected")
        async def protected_route(user: CurrentUser):
            return {"user_id": str(user.id)}
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        payload = decode_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user


# Type alias for clean route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Permission Checks ────────────────────────────────────────────


class RequirePermission:
    """Dependency that checks if the current user has the required permission.

    Usage:
        @router.post("/proposals/{id}/approve")
        async def approve_proposal(
            user: CurrentUser,
            _: Annotated[None, Depends(RequirePermission(Permission.APPROVE_PROPOSAL))],
        ):
            ...
    """

    def __init__(self, permission: Permission) -> None:
        self.permission = permission

    async def __call__(self, user: CurrentUser) -> None:
        try:
            user_role = UserRole(user.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {user.role}",
            )

        allowed_permissions = ROLE_PERMISSIONS.get(user_role, set())
        if self.permission not in allowed_permissions:
            logger.warning(
                "permission_denied",
                user_id=str(user.id),
                role=user.role,
                required=self.permission.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{self.permission.value}' required",
            )


class RequireRole:
    """Dependency that checks if the current user has the required role.

    Usage:
        @router.put("/system/config")
        async def update_config(
            user: CurrentUser,
            _: Annotated[None, Depends(RequireRole(UserRole.ADMIN))],
        ):
            ...
    """

    def __init__(self, *roles: UserRole) -> None:
        self.roles = roles

    async def __call__(self, user: CurrentUser) -> None:
        try:
            user_role = UserRole(user.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {user.role}",
            )

        if user_role not in self.roles:
            logger.warning(
                "role_denied",
                user_id=str(user.id),
                role=user.role,
                required=[r.value for r in self.roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {' or '.join(r.value for r in self.roles)} required",
            )


# ── Convenience Dependencies ─────────────────────────────────────

RequireAdmin = Depends(RequireRole(UserRole.ADMIN))
RequireTrader = Depends(RequireRole(UserRole.ADMIN, UserRole.TRADER))
RequireViewer = Depends(RequireRole(UserRole.ADMIN, UserRole.TRADER, UserRole.VIEWER))
