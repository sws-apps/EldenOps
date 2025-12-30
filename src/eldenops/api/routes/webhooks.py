"""Webhook receiver endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from eldenops.api.deps import get_db
from eldenops.api.websocket import get_manager
from eldenops.db.models.github import GitHubConnection
from eldenops.integrations.github.webhook import (
    parse_webhook_event,
    verify_webhook_signature,
)
from eldenops.tasks.github_tasks import process_github_event

logger = structlog.get_logger()
router = APIRouter()


@router.post("/github/{tenant_id}/{connection_id}")
async def github_webhook(
    tenant_id: str,
    connection_id: str,
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive GitHub webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Parses the event
    3. Queues it for processing
    """
    # Get raw body for signature verification
    body = await request.body()

    # Fetch webhook secret from database for this connection
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning(
            "GitHub connection not found",
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )

    # Verify signature if webhook secret is configured
    if connection.webhook_secret and x_hub_signature_256:
        if not verify_webhook_signature(body, x_hub_signature_256, connection.webhook_secret):
            logger.warning(
                "Invalid webhook signature",
                tenant_id=tenant_id,
                connection_id=connection_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    # Parse the event
    payload = await request.json()
    parsed = parse_webhook_event(x_github_event, payload)

    if parsed is None or parsed.get("skip"):
        logger.debug(
            "Skipping webhook event",
            event_type=x_github_event,
            reason=parsed.get("reason") if parsed else "unhandled event",
        )
        return {"status": "skipped"}

    logger.info(
        "Received GitHub webhook",
        tenant_id=tenant_id,
        connection_id=connection_id,
        event_type=x_github_event,
    )

    # Add repo info to parsed data
    parsed["repo_full_name"] = connection.repo_full_name

    # Process the event (can be async via task queue in production)
    try:
        await process_github_event(
            ctx={},
            tenant_id=tenant_id,
            connection_id=connection_id,
            event_data=parsed,
        )

        # Broadcast GitHub event via WebSocket for real-time updates
        manager = get_manager()
        await manager.broadcast_github_event(
            tenant_id,
            {
                "event_type": x_github_event,
                "repo_full_name": connection.repo_full_name,
                "title": parsed.get("title"),
                "user": parsed.get("user"),
                "url": parsed.get("url"),
            }
        )
    except Exception as e:
        logger.error(
            "Failed to process GitHub event",
            error=str(e),
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        # Still return accepted - we don't want GitHub to retry
        return {"status": "accepted", "warning": "processing_error"}

    return {"status": "accepted"}


@router.post("/discord/{tenant_id}")
async def discord_webhook(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive Discord webhook events (if using Discord webhooks).

    Note: Most Discord events come through the bot gateway, not webhooks.
    This is for optional webhook-based integrations (e.g., interactions).
    """
    payload = await request.json()

    event_type = payload.get("type")

    logger.info(
        "Received Discord webhook",
        tenant_id=tenant_id,
        event_type=event_type,
    )

    # Handle Discord interaction verification (ping)
    if event_type == 1:  # PING
        return {"type": 1}  # PONG

    # For other events, we typically handle them via the bot gateway
    # This endpoint is primarily for Discord Application Commands interactions
    # that don't go through the gateway

    return {"status": "accepted"}
