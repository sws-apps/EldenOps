"""Tenant management endpoints."""

from __future__ import annotations

from typing import Optional,  Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from eldenops.api.deps import CurrentUser, DBSession, TenantID, TenantMembership
from eldenops.core.security import encrypt_api_key, decrypt_api_key
from eldenops.db.models.tenant import Tenant, TenantMember, AIProviderConfig
from eldenops.db.models.discord import MonitoredChannel
from eldenops.db.models.github import GitHubConnection

logger = structlog.get_logger()
router = APIRouter()


class TenantResponse(BaseModel):
    """Tenant response schema."""

    id: str
    discord_guild_id: int
    guild_name: Optional[str]
    settings: dict[str, Any]
    is_active: bool


class TenantListResponse(BaseModel):
    """List of tenants response."""

    tenants: list[TenantResponse]
    total: int


class TenantUpdateRequest(BaseModel):
    """Tenant update request."""

    settings: Optional[dict[str, Any]] = None


class ChannelConfigResponse(BaseModel):
    """Channel configuration response."""

    id: str
    channel_id: int
    channel_name: Optional[str]
    channel_type: str
    is_active: bool


class GitHubConnectionResponse(BaseModel):
    """GitHub connection response."""

    id: str
    repo_full_name: str
    is_active: bool
    last_synced_at: Optional[str]


class AIProviderConfigResponse(BaseModel):
    """AI provider configuration response."""

    id: str
    provider: str
    is_default: bool
    is_active: bool


@router.get("")
async def list_tenants(
    current_user: CurrentUser,
    db: DBSession,
) -> TenantListResponse:
    """List all tenants the current user has access to."""
    user_id = current_user.get("user_id")
    logger.info("Listing tenants for user", user_id=user_id)

    # Query user's tenant memberships with tenant data
    result = await db.execute(
        select(TenantMember)
        .where(TenantMember.user_id == user_id)
        .options(selectinload(TenantMember.tenant))
    )
    memberships = result.scalars().all()

    tenants = [
        TenantResponse(
            id=m.tenant.id,
            discord_guild_id=m.tenant.discord_guild_id,
            guild_name=m.tenant.guild_name,
            settings=m.tenant.settings,
            is_active=m.tenant.is_active,
        )
        for m in memberships
        if m.tenant.is_active
    ]

    return TenantListResponse(tenants=tenants, total=len(tenants))


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: TenantID,
    db: DBSession,
) -> TenantResponse:
    """Get tenant details."""
    logger.info("Getting tenant", tenant_id=tenant_id)

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return TenantResponse(
        id=tenant.id,
        discord_guild_id=tenant.discord_guild_id,
        guild_name=tenant.guild_name,
        settings=tenant.settings,
        is_active=tenant.is_active,
    )


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: TenantID,
    request: TenantUpdateRequest,
    membership: TenantMembership,
    db: DBSession,
) -> TenantResponse:
    """Update tenant settings (admin only)."""
    # Verify user is admin
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    logger.info("Updating tenant", tenant_id=tenant_id)

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Update settings
    if request.settings is not None:
        tenant.settings = {**tenant.settings, **request.settings}

    await db.flush()

    return TenantResponse(
        id=tenant.id,
        discord_guild_id=tenant.discord_guild_id,
        guild_name=tenant.guild_name,
        settings=tenant.settings,
        is_active=tenant.is_active,
    )


# Channel configuration endpoints
@router.get("/{tenant_id}/channels")
async def list_channels(
    tenant_id: TenantID,
    db: DBSession,
) -> list[ChannelConfigResponse]:
    """List monitored channels for a tenant."""
    result = await db.execute(
        select(MonitoredChannel).where(MonitoredChannel.tenant_id == tenant_id)
    )
    channels = result.scalars().all()

    return [
        ChannelConfigResponse(
            id=ch.id,
            channel_id=ch.channel_id,
            channel_name=ch.channel_name,
            channel_type=ch.channel_type,
            is_active=ch.is_active,
        )
        for ch in channels
    ]


class AddChannelRequest(BaseModel):
    """Request to add a channel."""
    channel_id: int
    channel_name: Optional[str] = None
    channel_type: str = "text"


@router.post("/{tenant_id}/channels")
async def add_channel(
    tenant_id: TenantID,
    request: AddChannelRequest,
    membership: TenantMembership,
    db: DBSession,
) -> ChannelConfigResponse:
    """Add a channel to monitor."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Check if channel already exists
    result = await db.execute(
        select(MonitoredChannel).where(
            MonitoredChannel.tenant_id == tenant_id,
            MonitoredChannel.channel_id == request.channel_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel already monitored",
        )

    channel = MonitoredChannel(
        tenant_id=tenant_id,
        channel_id=request.channel_id,
        channel_name=request.channel_name,
        channel_type=request.channel_type,
    )
    db.add(channel)
    await db.flush()

    return ChannelConfigResponse(
        id=channel.id,
        channel_id=channel.channel_id,
        channel_name=channel.channel_name,
        channel_type=channel.channel_type,
        is_active=channel.is_active,
    )


@router.delete("/{tenant_id}/channels/{channel_id}")
async def remove_channel(
    tenant_id: TenantID,
    channel_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Remove a channel from monitoring."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(MonitoredChannel).where(
            MonitoredChannel.tenant_id == tenant_id,
            MonitoredChannel.id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    await db.delete(channel)
    return {"message": "Channel removed"}


# GitHub connection endpoints
@router.get("/{tenant_id}/github")
async def list_github_connections(
    tenant_id: TenantID,
    db: DBSession,
) -> list[GitHubConnectionResponse]:
    """List GitHub connections for a tenant."""
    result = await db.execute(
        select(GitHubConnection).where(GitHubConnection.tenant_id == tenant_id)
    )
    connections = result.scalars().all()

    return [
        GitHubConnectionResponse(
            id=conn.id,
            repo_full_name=conn.repo_full_name,
            is_active=conn.is_active,
            last_synced_at=conn.last_synced_at.isoformat() if conn.last_synced_at else None,
        )
        for conn in connections
    ]


class AddGitHubConnectionRequest(BaseModel):
    """Request to add a GitHub connection."""
    repo_full_name: str  # e.g., "owner/repo"


@router.post("/{tenant_id}/github")
async def add_github_connection(
    tenant_id: TenantID,
    request: AddGitHubConnectionRequest,
    membership: TenantMembership,
    current_user: CurrentUser,
    db: DBSession,
) -> GitHubConnectionResponse:
    """Connect a GitHub repository."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Parse repo name
    parts = request.repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repo format. Expected 'owner/repo'",
        )

    org_name, repo_name = parts

    # Check if connection already exists
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.repo_full_name == request.repo_full_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected",
        )

    # Create connection (webhook creation would be done separately via GitHub App)
    connection = GitHubConnection(
        tenant_id=tenant_id,
        connected_by_user_id=current_user.get("user_id"),
        org_name=org_name,
        repo_name=repo_name,
        repo_full_name=request.repo_full_name,
    )
    db.add(connection)
    await db.flush()

    logger.info(
        "GitHub connection created",
        tenant_id=tenant_id,
        repo=request.repo_full_name,
    )

    return GitHubConnectionResponse(
        id=connection.id,
        repo_full_name=connection.repo_full_name,
        is_active=connection.is_active,
        last_synced_at=None,
    )


@router.delete("/{tenant_id}/github/{connection_id}")
async def remove_github_connection(
    tenant_id: TenantID,
    connection_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Disconnect a GitHub repository."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.id == connection_id,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub connection not found",
        )

    # Note: Webhook removal would be handled by GitHub App uninstall or manual cleanup
    await db.delete(connection)

    logger.info(
        "GitHub connection removed",
        tenant_id=tenant_id,
        connection_id=connection_id,
    )

    return {"message": "GitHub connection removed"}


# AI provider configuration endpoints
@router.get("/{tenant_id}/ai-providers")
async def list_ai_providers(
    tenant_id: TenantID,
    db: DBSession,
) -> list[AIProviderConfigResponse]:
    """List AI provider configurations for a tenant."""
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id)
    )
    configs = result.scalars().all()

    return [
        AIProviderConfigResponse(
            id=cfg.id,
            provider=cfg.provider,
            is_default=cfg.is_default,
            is_active=cfg.is_active,
        )
        for cfg in configs
    ]


class AddAIProviderRequest(BaseModel):
    """Request to add an AI provider."""
    provider: str  # e.g., "claude", "openai", "gemini"
    api_key: str
    is_default: bool = False


@router.post("/{tenant_id}/ai-providers")
async def add_ai_provider(
    tenant_id: TenantID,
    request: AddAIProviderRequest,
    membership: TenantMembership,
    db: DBSession,
) -> AIProviderConfigResponse:
    """Configure an AI provider for a tenant."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Validate provider
    valid_providers = ["claude", "openai", "gemini", "deepseek"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
        )

    # Check if provider already configured
    result = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.tenant_id == tenant_id,
            AIProviderConfig.provider == request.provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider already configured",
        )

    # If setting as default, unset other defaults
    if request.is_default:
        await db.execute(
            select(AIProviderConfig)
            .where(AIProviderConfig.tenant_id == tenant_id)
        )
        current_configs = (await db.execute(
            select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id)
        )).scalars().all()
        for cfg in current_configs:
            cfg.is_default = False

    # Encrypt API key and create config
    encrypted_key = encrypt_api_key(request.api_key)

    config = AIProviderConfig(
        tenant_id=tenant_id,
        provider=request.provider,
        api_key_encrypted=encrypted_key,
        is_default=request.is_default,
    )
    db.add(config)
    await db.flush()

    logger.info(
        "AI provider configured",
        tenant_id=tenant_id,
        provider=request.provider,
    )

    return AIProviderConfigResponse(
        id=config.id,
        provider=config.provider,
        is_default=config.is_default,
        is_active=config.is_active,
    )


class UpdateAIProviderRequest(BaseModel):
    """Request to update an AI provider."""
    api_key: Optional[str] = None
    is_default: Optional[bool] = None


@router.put("/{tenant_id}/ai-providers/{provider_id}")
async def update_ai_provider(
    tenant_id: TenantID,
    provider_id: str,
    request: UpdateAIProviderRequest,
    membership: TenantMembership,
    db: DBSession,
) -> AIProviderConfigResponse:
    """Update an AI provider configuration."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.tenant_id == tenant_id,
            AIProviderConfig.id == provider_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI provider configuration not found",
        )

    # Update API key if provided
    if request.api_key is not None:
        config.api_key_encrypted = encrypt_api_key(request.api_key)

    # Update default status if provided
    if request.is_default is not None:
        if request.is_default:
            # Unset other defaults
            current_configs = (await db.execute(
                select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id)
            )).scalars().all()
            for cfg in current_configs:
                cfg.is_default = False
        config.is_default = request.is_default

    await db.flush()

    logger.info(
        "AI provider updated",
        tenant_id=tenant_id,
        provider=config.provider,
    )

    return AIProviderConfigResponse(
        id=config.id,
        provider=config.provider,
        is_default=config.is_default,
        is_active=config.is_active,
    )


@router.delete("/{tenant_id}/ai-providers/{provider_id}")
async def delete_ai_provider(
    tenant_id: TenantID,
    provider_id: str,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Delete an AI provider configuration."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.tenant_id == tenant_id,
            AIProviderConfig.id == provider_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI provider configuration not found",
        )

    await db.delete(config)

    logger.info(
        "AI provider deleted",
        tenant_id=tenant_id,
        provider_id=provider_id,
    )

    return {"message": "AI provider configuration deleted"}


# GitHub token configuration endpoints
class GitHubTokenStatusResponse(BaseModel):
    """GitHub token status response."""
    is_configured: bool
    is_valid: Optional[bool] = None
    token_preview: Optional[str] = None  # First 4 chars for identification


class SetGitHubTokenRequest(BaseModel):
    """Request to set GitHub token."""
    token: str


@router.get("/{tenant_id}/github-token")
async def get_github_token_status(
    tenant_id: TenantID,
    db: DBSession,
) -> GitHubTokenStatusResponse:
    """Check if GitHub token is configured for a tenant."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    if not tenant.github_token_encrypted:
        return GitHubTokenStatusResponse(is_configured=False)

    # Decrypt and get preview
    try:
        token = decrypt_api_key(tenant.github_token_encrypted)
        token_preview = token[:4] + "..." if len(token) > 4 else "***"

        # Optionally validate token (quick check)
        from eldenops.integrations.github.client import GitHubClient
        client = GitHubClient(token)
        is_valid = await client.validate_token()
        await client.close()

        return GitHubTokenStatusResponse(
            is_configured=True,
            is_valid=is_valid,
            token_preview=token_preview,
        )
    except Exception as e:
        logger.error("Error checking GitHub token", error=str(e))
        return GitHubTokenStatusResponse(
            is_configured=True,
            is_valid=False,
            token_preview="****",
        )


@router.post("/{tenant_id}/github-token")
async def set_github_token(
    tenant_id: TenantID,
    request: SetGitHubTokenRequest,
    membership: TenantMembership,
    db: DBSession,
) -> GitHubTokenStatusResponse:
    """Set or update GitHub token for a tenant."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Validate token before saving
    from eldenops.integrations.github.client import GitHubClient
    client = GitHubClient(request.token)
    is_valid = await client.validate_token()
    await client.close()

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub token. Please check the token and try again.",
        )

    # Encrypt and save
    tenant.github_token_encrypted = encrypt_api_key(request.token)
    await db.flush()

    logger.info("GitHub token configured", tenant_id=tenant_id)

    token_preview = request.token[:4] + "..." if len(request.token) > 4 else "***"

    return GitHubTokenStatusResponse(
        is_configured=True,
        is_valid=True,
        token_preview=token_preview,
    )


@router.delete("/{tenant_id}/github-token")
async def remove_github_token(
    tenant_id: TenantID,
    membership: TenantMembership,
    db: DBSession,
) -> dict:
    """Remove GitHub token for a tenant."""
    if not membership.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant.github_token_encrypted = None
    await db.flush()

    logger.info("GitHub token removed", tenant_id=tenant_id)

    return {"message": "GitHub token removed"}
