"""Discord-related background tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
import structlog

from eldenops.ai.router import analyze_with_ai
from eldenops.config.constants import DiscordEventType
from eldenops.db.engine import get_session
from eldenops.db.models.discord import DiscordEvent
from eldenops.db.models.user import User

logger = structlog.get_logger()


async def process_discord_event(
    ctx: dict,
    tenant_id: str,
    event_type: str,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process a Discord event and store it in the database.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        event_type: Type of Discord event
        event_data: Event metadata

    Returns:
        Processing result
    """
    logger.info(
        "Processing Discord event",
        tenant_id=tenant_id,
        event_type=event_type,
    )

    async with get_session() as db:
        # Look up user by Discord ID if provided
        user_id = None
        if discord_user_id := event_data.get("discord_user_id"):
            result = await db.execute(
                select(User).where(User.discord_id == discord_user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user_id = user.id

        # Parse timestamp
        timestamp = event_data.get("timestamp")
        if isinstance(timestamp, str):
            created_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            created_at = datetime.now(timezone.utc)

        # Create DiscordEvent record
        event = DiscordEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            channel_id=event_data.get("channel_id"),
            message_id=event_data.get("message_id"),
            word_count=event_data.get("word_count"),
            has_attachments=event_data.get("has_attachments", False),
            has_links=event_data.get("has_links", False),
            has_mentions=event_data.get("has_mentions", False),
            is_reply=event_data.get("is_reply", False),
            thread_id=event_data.get("thread_id"),
            metadata=event_data.get("metadata", {}),
            created_at=created_at,
        )
        db.add(event)

    logger.info(
        "Discord event stored",
        tenant_id=tenant_id,
        event_type=event_type,
    )

    return {
        "status": "processed",
        "tenant_id": tenant_id,
        "event_type": event_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


async def analyze_discord_activity(
    ctx: dict,
    tenant_id: str,
    channel_id: int,
    days: int = 7,
) -> dict[str, Any]:
    """Analyze Discord activity for a channel using AI.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        channel_id: Discord channel ID
        days: Number of days to analyze

    Returns:
        Analysis results
    """
    logger.info(
        "Analyzing Discord activity",
        tenant_id=tenant_id,
        channel_id=channel_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_session() as db:
        # Fetch events from database
        result = await db.execute(
            select(DiscordEvent)
            .where(
                DiscordEvent.tenant_id == tenant_id,
                DiscordEvent.channel_id == channel_id,
                DiscordEvent.created_at >= since,
            )
            .order_by(DiscordEvent.created_at)
        )
        events = result.scalars().all()

        # Get aggregate stats
        stats_result = await db.execute(
            select(
                func.count(DiscordEvent.id).label("total_events"),
                func.count(func.distinct(DiscordEvent.user_id)).label("unique_users"),
                func.sum(DiscordEvent.word_count).label("total_words"),
            )
            .where(
                DiscordEvent.tenant_id == tenant_id,
                DiscordEvent.channel_id == channel_id,
                DiscordEvent.created_at >= since,
            )
        )
        stats = stats_result.one()

    if not events:
        return {
            "status": "completed",
            "channel_id": channel_id,
            "analysis": "No activity found for this period.",
            "stats": {"total_events": 0, "unique_users": 0, "total_words": 0},
        }

    # Build summary for AI
    event_summary = f"""
Discord Channel Activity Summary (last {days} days):
- Total messages/events: {stats.total_events}
- Unique users: {stats.unique_users}
- Total words: {stats.total_words or 0}

Event types breakdown:
"""
    # Count by event type
    type_counts: dict[str, int] = {}
    for event in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    for event_type, count in type_counts.items():
        event_summary += f"- {event_type}: {count}\n"

    # Send to AI for analysis
    ai_response = await analyze_with_ai(
        prompt=f"""Analyze this Discord channel activity and provide insights:

{event_summary}

Please provide:
1. Activity patterns and trends
2. Engagement level assessment
3. Suggestions for improving community engagement
""",
        system_prompt="You are an analytics assistant specializing in community engagement analysis. Provide concise, actionable insights.",
        max_tokens=1024,
        temperature=0.5,
    )

    return {
        "status": "completed",
        "channel_id": channel_id,
        "analysis": ai_response.content,
        "stats": {
            "total_events": stats.total_events,
            "unique_users": stats.unique_users,
            "total_words": stats.total_words or 0,
        },
        "tokens_used": ai_response.usage.total_tokens if ai_response.usage else None,
    }
