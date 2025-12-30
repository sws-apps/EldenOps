"""Attendance event handlers for tracking check-ins, check-outs, and breaks."""

from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant
from eldenops.db.models.discord import MonitoredChannel
from eldenops.services.attendance import AttendanceService

logger = structlog.get_logger()

# Channel names that should be monitored for attendance
ATTENDANCE_CHANNEL_NAMES = [
    "checkin-status",
    "check-in-status",
    "attendance",
    "extended-breaks",
    "breaks",
]


class AttendanceEvents(commands.Cog):
    """Handles attendance message events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_attendance_channel(self, channel: discord.TextChannel) -> bool:
        """Check if a channel is an attendance tracking channel."""
        if not channel.name:
            return False

        channel_name = channel.name.lower().replace("_", "-")
        return any(
            name in channel_name for name in ATTENDANCE_CHANNEL_NAMES
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Track attendance messages in designated channels."""
        # Ignore DMs
        if not message.guild:
            return

        # Ignore bot messages
        if message.author.bot:
            return

        # Check if this is an attendance channel
        if not self._is_attendance_channel(message.channel):
            return

        async with get_session() as db:
            # Get tenant for this guild
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == message.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                logger.debug(
                    "No active tenant for guild",
                    guild_id=message.guild.id,
                    guild_name=message.guild.name,
                )
                return

            # Process the message through attendance service
            service = AttendanceService(db)

            try:
                log = await service.process_message(
                    tenant_id=tenant.id,
                    discord_user_id=message.author.id,
                    channel_id=message.channel.id,
                    message_id=message.id,
                    message_content=message.content,
                    message_time=message.created_at.replace(tzinfo=timezone.utc),
                )

                if log:
                    await db.commit()
                    logger.info(
                        "Attendance event processed",
                        event_type=log.event_type,
                        user=message.author.name,
                        channel=message.channel.name,
                        guild=message.guild.name,
                    )

                    # Optional: React to confirm the message was processed
                    await self._add_confirmation_reaction(message, log.event_type)

            except Exception as e:
                logger.error(
                    "Failed to process attendance message",
                    error=str(e),
                    message_content=message.content[:50],
                    user=message.author.name,
                )
                await db.rollback()

    async def _add_confirmation_reaction(
        self, message: discord.Message, event_type: str
    ) -> None:
        """Add a reaction to confirm the attendance event was recorded."""
        try:
            # Map event types to emojis
            emoji_map = {
                "checkin": "👋",
                "checkout": "🌙",
                "break_start": "☕",
                "break_end": "💪",
            }

            emoji = emoji_map.get(event_type)
            if emoji:
                await message.add_reaction(emoji)
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass
        except Exception as e:
            logger.debug("Could not add reaction", error=str(e))


async def setup(bot: commands.Bot) -> None:
    """Load the AttendanceEvents cog."""
    await bot.add_cog(AttendanceEvents(bot))
