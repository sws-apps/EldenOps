"""Message event handlers for tracking Discord activity."""

from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.config.constants import DiscordEventType
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant
from eldenops.db.models.discord import MonitoredChannel, DiscordEvent
from eldenops.db.models.user import User

logger = structlog.get_logger()


class MessageEvents(commands.Cog):
    """Handles message events for activity tracking."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Track message metadata (not content) for monitored channels."""
        # Ignore DMs
        if not message.guild:
            return

        # Ignore bot messages
        if message.author.bot:
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
                return

            # Check if channel is monitored for this tenant
            channel_id = message.channel.parent_id if isinstance(message.channel, discord.Thread) else message.channel.id
            monitored_result = await db.execute(
                select(MonitoredChannel).where(
                    MonitoredChannel.tenant_id == tenant.id,
                    MonitoredChannel.channel_id == channel_id,
                    MonitoredChannel.is_active == True,
                )
            )
            monitored_channel = monitored_result.scalar_one_or_none()

            if not monitored_channel:
                return

            # Look up user
            user_result = await db.execute(
                select(User).where(User.discord_id == message.author.id)
            )
            user = user_result.scalar_one_or_none()
            user_id = user.id if user else None

            # Extract metadata only (no message content for privacy)
            now = datetime.now(timezone.utc)

            # Create and store event directly
            event = DiscordEvent(
                tenant_id=tenant.id,
                user_id=user_id,
                event_type=DiscordEventType.MESSAGE,
                channel_id=message.channel.id,
                message_id=message.id,
                word_count=len(message.content.split()) if message.content else 0,
                has_attachments=len(message.attachments) > 0,
                has_links="http" in message.content.lower() if message.content else False,
                has_mentions=len(message.mentions) > 0 or len(message.role_mentions) > 0,
                is_reply=message.reference is not None,
                thread_id=message.channel.id if isinstance(message.channel, discord.Thread) else None,
                event_metadata={"discord_user_id": message.author.id},
                created_at=now,
            )
            db.add(event)

        logger.debug(
            "Message activity stored",
            event_type=DiscordEventType.MESSAGE,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Track message edits."""
        if not after.guild or after.author.bot:
            return

        logger.debug(
            "Message edit tracked",
            event_type=DiscordEventType.MESSAGE_EDIT,
            guild_id=after.guild.id,
            channel_id=after.channel.id,
            message_id=after.id,
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Track message deletions."""
        if not message.guild or message.author.bot:
            return

        logger.debug(
            "Message deletion tracked",
            event_type=DiscordEventType.MESSAGE_DELETE,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
        )

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User | discord.Member
    ) -> None:
        """Track reaction additions."""
        if not reaction.message.guild or user.bot:
            return

        logger.debug(
            "Reaction tracked",
            event_type=DiscordEventType.REACTION_ADD,
            guild_id=reaction.message.guild.id,
            channel_id=reaction.message.channel.id,
            message_id=reaction.message.id,
            user_id=user.id,
        )

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Track thread creation."""
        if not thread.guild:
            return

        logger.debug(
            "Thread created",
            event_type=DiscordEventType.THREAD_CREATE,
            guild_id=thread.guild.id,
            channel_id=thread.parent_id,
            thread_id=thread.id,
            thread_name=thread.name,
        )


async def setup(bot: commands.Bot) -> None:
    """Load the MessageEvents cog."""
    await bot.add_cog(MessageEvents(bot))
