"""Authentication endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from eldenops.api.deps import CurrentUser, get_db
from eldenops.config.settings import settings
from eldenops.core.security import create_access_token, create_refresh_token, verify_refresh_token
from eldenops.db.models.user import User
from eldenops.db.models.tenant import Tenant, TenantMember

logger = structlog.get_logger()
router = APIRouter()

DISCORD_API_URL = "https://discord.com/api/v10"


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class UserResponse(BaseModel):
    """User info response."""

    id: str
    discord_id: int
    discord_username: Optional[str]
    email: Optional[str]
    github_username: Optional[str]


class TenantInfo(BaseModel):
    """Tenant info for switcher."""

    id: str
    guild_name: str
    guild_icon_url: Optional[str]
    role: str  # User's role in this tenant


class UserTenantsResponse(BaseModel):
    """User's tenants response."""

    tenants: list[TenantInfo]
    current_tenant_id: Optional[str]


class SwitchTenantRequest(BaseModel):
    """Switch tenant request."""

    tenant_id: str


@router.get("/discord/url")
async def get_discord_oauth_url() -> dict:
    """Get Discord OAuth2 authorization URL."""
    from eldenops.config.settings import settings

    # Discord OAuth2 URL
    base_url = "https://discord.com/api/oauth2/authorize"
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
    }

    url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    return {"url": url}


@router.get("/discord/callback")
async def discord_oauth_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Handle Discord OAuth2 callback.

    Exchanges the authorization code for tokens and creates/updates user.
    """
    logger.info("Discord OAuth callback received", code_length=len(code))

    async with httpx.AsyncClient() as client:
        # 1. Exchange code for Discord access token
        token_response = await client.post(
            f"{DISCORD_API_URL}/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret.get_secret_value(),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            logger.error("Discord token exchange failed", status=token_response.status_code)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code",
            )

        token_data = token_response.json()
        discord_access_token = token_data["access_token"]

        # 2. Fetch user info from Discord
        user_response = await client.get(
            f"{DISCORD_API_URL}/users/@me",
            headers={"Authorization": f"Bearer {discord_access_token}"},
        )

        if user_response.status_code != 200:
            logger.error("Discord user fetch failed", status=user_response.status_code)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch user info from Discord",
            )

        discord_user = user_response.json()

    # 3. Create or update user in database
    discord_id = int(discord_user["id"])
    result = await db.execute(
        select(User).where(User.discord_id == discord_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.discord_username = discord_user.get("username")
        if discord_user.get("avatar"):
            user.discord_avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{discord_user['avatar']}.png"
        if discord_user.get("email"):
            user.email = discord_user["email"]
            user.email_verified = discord_user.get("verified", False)
    else:
        # Create new user
        avatar_url = None
        if discord_user.get("avatar"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{discord_user['avatar']}.png"

        user = User(
            discord_id=discord_id,
            discord_username=discord_user.get("username"),
            discord_avatar_url=avatar_url,
            email=discord_user.get("email"),
            email_verified=discord_user.get("verified", False),
        )
        db.add(user)

    await db.flush()

    # Get user's primary tenant and role
    membership_result = await db.execute(
        select(TenantMember).where(TenantMember.user_id == user.id).limit(1)
    )
    membership = membership_result.scalar_one_or_none()
    primary_tenant_id = membership.tenant_id if membership else None
    user_role = membership.role if membership else None

    logger.info("User authenticated", user_id=user.id, discord_id=discord_id, role=user_role)

    # 4. Generate our JWT tokens
    user_data = {
        "user_id": user.id,
        "discord_id": user.discord_id,
        "discord_username": user.discord_username,
        "primary_tenant_id": primary_tenant_id,
        "role": user_role,
    }

    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token({
        "user_id": user.id,
        "discord_id": user.discord_id,
        "tenant_id": str(primary_tenant_id) if primary_tenant_id else None,
    })

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh")
async def refresh_tokens(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using refresh token."""
    try:
        payload = verify_refresh_token(request.refresh_token)
        user_id = payload.get("user_id")
        stored_tenant_id = payload.get("tenant_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # Fetch user from database to get current data
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Use stored tenant if available, otherwise get first tenant
        if stored_tenant_id:
            # Verify user still has access to this tenant
            membership_result = await db.execute(
                select(TenantMember).where(
                    TenantMember.user_id == user.id,
                    TenantMember.tenant_id == stored_tenant_id,
                )
            )
            membership = membership_result.scalar_one_or_none()
            primary_tenant_id = stored_tenant_id if membership else None
        else:
            primary_tenant_id = None

        # Fallback to first tenant if stored one is invalid
        if not primary_tenant_id:
            membership_result = await db.execute(
                select(TenantMember).where(TenantMember.user_id == user.id).limit(1)
            )
            membership = membership_result.scalar_one_or_none()
            primary_tenant_id = membership.tenant_id if membership else None

        # Get user's role in the current tenant
        user_role = None
        if primary_tenant_id:
            role_result = await db.execute(
                select(TenantMember.role).where(
                    TenantMember.user_id == user.id,
                    TenantMember.tenant_id == primary_tenant_id,
                )
            )
            user_role = role_result.scalar_one_or_none()

        user_data = {
            "user_id": user.id,
            "discord_id": user.discord_id,
            "discord_username": user.discord_username,
            "primary_tenant_id": primary_tenant_id,
            "role": user_role,
        }

        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token({
            "user_id": user.id,
            "discord_id": user.discord_id,
            "tenant_id": str(primary_tenant_id) if primary_tenant_id else None,
        })

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from e


@router.get("/me")
async def get_current_user_info(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get current authenticated user's information."""
    user_id = current_user.get("user_id")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=user.id,
        discord_id=user.discord_id,
        discord_username=user.discord_username,
        email=user.email,
        github_username=user.github_username,
    )


@router.post("/logout")
async def logout(current_user: CurrentUser) -> dict:
    """Logout current user.

    Note: With JWT, we can't truly invalidate tokens server-side without
    a token blacklist. The client should discard the tokens.
    """
    logger.info("User logged out", user_id=current_user.get("user_id"))
    return {"message": "Logged out successfully"}


@router.get("/tenants")
async def get_user_tenants(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserTenantsResponse:
    """Get all tenants the user belongs to."""
    user_id = current_user.get("user_id")
    current_tenant_id = current_user.get("primary_tenant_id")

    # Get all memberships with tenant info
    result = await db.execute(
        select(TenantMember, Tenant)
        .join(Tenant, TenantMember.tenant_id == Tenant.id)
        .where(TenantMember.user_id == user_id, Tenant.is_active == True)
    )
    rows = result.all()

    tenants = [
        TenantInfo(
            id=str(tenant.id),
            guild_name=tenant.guild_name,
            guild_icon_url=tenant.guild_icon_url,
            role=membership.role,
        )
        for membership, tenant in rows
    ]

    return UserTenantsResponse(
        tenants=tenants,
        current_tenant_id=str(current_tenant_id) if current_tenant_id else None,
    )


@router.post("/tenants/switch")
async def switch_tenant(
    request: SwitchTenantRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Switch to a different tenant and get new tokens."""
    user_id = current_user.get("user_id")

    # Verify user has access to this tenant
    result = await db.execute(
        select(TenantMember)
        .where(
            TenantMember.user_id == user_id,
            TenantMember.tenant_id == request.tenant_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this tenant",
        )

    # Get user info
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    # Generate new tokens with the selected tenant and role
    user_data = {
        "user_id": user.id,
        "discord_id": user.discord_id,
        "discord_username": user.discord_username,
        "primary_tenant_id": request.tenant_id,
        "role": membership.role,
    }

    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token({
        "user_id": user.id,
        "discord_id": user.discord_id,
        "tenant_id": request.tenant_id,
    })

    logger.info("User switched tenant", user_id=user_id, tenant_id=request.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )
