"""Voice channel event handlers."""

from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select, update
import structlog

from eldenops.config.constants import DiscordEventType
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant
from eldenops.db.models.discord import VoiceSession
from eldenops.db.models.user import User

logger = structlog.get_logger()


class VoiceEvents(commands.Cog):
    """Handles voice state events for attendance tracking."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Track active sessions: {(guild_id, user_id): session_start_time}
        self._active_sessions: dict[tuple[int, int], datetime] = {}

    async def _get_tenant_and_user(self, guild_id: int, discord_user_id: int, db) -> Tuple[Optional[str], Optional[str]]:
        """Helper to get tenant_id and user_id from guild and discord IDs."""
        tenant_result = await db.execute(
            select(Tenant).where(
                Tenant.discord_guild_id == guild_id,
                Tenant.is_active == True,
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return None, None

        user_result = await db.execute(
            select(User).where(User.discord_id == discord_user_id)
        )
        user = user_result.scalar_one_or_none()
        user_id = user.id if user else None

        return tenant.id, user_id

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Track voice channel joins, leaves, and moves."""
        if member.bot:
            return

        guild_id = member.guild.id
        discord_user_id = member.id
        session_key = (guild_id, discord_user_id)
        now = datetime.now(timezone.utc)

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            logger.debug(
                "Voice join tracked",
                event_type=DiscordEventType.VOICE_JOIN,
                guild_id=guild_id,
                user_id=discord_user_id,
                channel_id=after.channel.id,
                channel_name=after.channel.name,
            )

            # Start tracking session locally
            self._active_sessions[session_key] = now

            # Create voice session in database
            async with get_session() as db:
                tenant_id, user_id = await self._get_tenant_and_user(guild_id, discord_user_id, db)
                if tenant_id:
                    session = VoiceSession(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        channel_id=after.channel.id,
                        started_at=now,
                    )
                    db.add(session)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            # Calculate session duration
            session_start = self._active_sessions.pop(session_key, None)
            duration_seconds = 0
            if session_start:
                duration_seconds = int((now - session_start).total_seconds())

            logger.debug(
                "Voice leave tracked",
                event_type=DiscordEventType.VOICE_LEAVE,
                guild_id=guild_id,
                user_id=discord_user_id,
                channel_id=before.channel.id,
                channel_name=before.channel.name,
                duration_seconds=duration_seconds,
            )

            # Update voice session in database with end time and duration
            async with get_session() as db:
                tenant_id, user_id = await self._get_tenant_and_user(guild_id, discord_user_id, db)
                if tenant_id:
                    # Find the open session for this user/channel
                    result = await db.execute(
                        select(VoiceSession).where(
                            VoiceSession.tenant_id == tenant_id,
                            VoiceSession.channel_id == before.channel.id,
                            VoiceSession.ended_at == None,
                        ).order_by(VoiceSession.started_at.desc()).limit(1)
                    )
                    session = result.scalar_one_or_none()
                    if session:
                        session.ended_at = now
                        session.duration_seconds = duration_seconds

        # User moved between channels
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            # End session for previous channel
            session_start = self._active_sessions.get(session_key)
            duration_seconds = 0
            if session_start:
                duration_seconds = int((now - session_start).total_seconds())

            logger.debug(
                "Voice channel move tracked",
                guild_id=guild_id,
                user_id=discord_user_id,
                from_channel_id=before.channel.id,
                from_channel_name=before.channel.name,
                to_channel_id=after.channel.id,
                to_channel_name=after.channel.name,
                previous_duration_seconds=duration_seconds,
            )

            # Start new session for new channel
            self._active_sessions[session_key] = now

            # End previous session, create new session in database
            async with get_session() as db:
                tenant_id, user_id = await self._get_tenant_and_user(guild_id, discord_user_id, db)
                if tenant_id:
                    # End the previous session
                    result = await db.execute(
                        select(VoiceSession).where(
                            VoiceSession.tenant_id == tenant_id,
                            VoiceSession.channel_id == before.channel.id,
                            VoiceSession.ended_at == None,
                        ).order_by(VoiceSession.started_at.desc()).limit(1)
                    )
                    old_session = result.scalar_one_or_none()
                    if old_session:
                        old_session.ended_at = now
                        old_session.duration_seconds = duration_seconds

                    # Create new session
                    new_session = VoiceSession(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        channel_id=after.channel.id,
                        started_at=now,
                    )
                    db.add(new_session)

        # Track mute/deafen state changes (for engagement metrics)
        if before.self_mute != after.self_mute or before.self_deaf != after.self_deaf:
            logger.debug(
                "Voice state change",
                guild_id=guild_id,
                user_id=discord_user_id,
                muted=after.self_mute,
                deafened=after.self_deaf,
            )


async def setup(bot: commands.Bot) -> None:
    """Load the VoiceEvents cog."""
    await bot.add_cog(VoiceEvents(bot))
