"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eldenops.core.security import verify_access_token
from eldenops.db.engine import get_session_dependency
from eldenops.db.models.tenant import TenantMember


# Database session dependency
async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in get_session_dependency():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


# Authentication dependency
async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Get current authenticated user from JWT token.

    Returns user data from token payload.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        payload = verify_access_token(token)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


CurrentUser = Annotated[dict, Depends(get_current_user)]


# Optional authentication (for public + authenticated routes)
async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """Get current user if authenticated, None otherwise."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    try:
        return verify_access_token(token)
    except Exception:
        return None


OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]


# Tenant context dependency
async def get_tenant_id(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    x_tenant_id: Optional[str] = Header(default=None),
) -> str:
    """Get tenant ID from header or user's default tenant.

    For multi-tenant requests, the tenant ID must be provided.
    """
    user_id = current_user.get("user_id")

    if x_tenant_id:
        # Verify user has access to this tenant
        result = await db.execute(
            select(TenantMember).where(
                TenantMember.user_id == user_id,
                TenantMember.tenant_id == x_tenant_id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this tenant",
            )

        return x_tenant_id

    # Fall back to user's primary tenant
    primary_tenant = current_user.get("primary_tenant_id")
    if not primary_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header required or user must have a default tenant",
        )

    return primary_tenant


TenantID = Annotated[str, Depends(get_tenant_id)]


# Tenant membership with role info
async def get_tenant_membership(
    current_user: CurrentUser,
    tenant_id: TenantID,
    db: AsyncSession = Depends(get_db),
) -> TenantMember:
    """Get the user's membership for the current tenant with role info."""
    user_id = current_user.get("user_id")

    result = await db.execute(
        select(TenantMember).where(
            TenantMember.user_id == user_id,
            TenantMember.tenant_id == tenant_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this tenant",
        )

    return membership


TenantMembership = Annotated[TenantMember, Depends(get_tenant_membership)]
