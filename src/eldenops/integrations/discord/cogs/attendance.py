"""Attendance management commands."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant
from eldenops.services.attendance import AttendanceService

logger = structlog.get_logger()

# Channel names to look for
ATTENDANCE_CHANNEL_NAMES = [
    "checkin-status",
    "check-in-status",
    "attendance",
    "extended-breaks",
]


class AttendanceCog(commands.Cog):
    """Attendance management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_attendance_channel(self, channel: discord.TextChannel) -> bool:
        """Check if a channel is an attendance channel."""
        if not channel.name:
            return False
        channel_name = channel.name.lower().replace("_", "-")
        return any(name in channel_name for name in ATTENDANCE_CHANNEL_NAMES)

    @app_commands.command(name="attendance-sync", description="Sync today's attendance messages from this channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_attendance(self, interaction: discord.Interaction) -> None:
        """Import today's attendance messages from the current channel."""
        await interaction.response.defer(ephemeral=True)

        if not self._is_attendance_channel(interaction.channel):
            await interaction.followup.send(
                "This command must be run in an attendance channel "
                f"(like #checkin-status). Current channel: #{interaction.channel.name}",
                ephemeral=True,
            )
            return

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild_id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "No tenant found for this server. Please set up EldenOps first.",
                    ephemeral=True,
                )
                return

            # Get today's start (midnight in UTC)
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Fetch messages from today
            service = AttendanceService(db)
            processed = 0
            skipped = 0

            await interaction.followup.send(
                f"🔄 Scanning messages from today in #{interaction.channel.name}...",
                ephemeral=True,
            )

            async for message in interaction.channel.history(
                after=today_start,
                limit=500,
                oldest_first=True,
            ):
                # Skip bot messages
                if message.author.bot:
                    continue

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
                        processed += 1
                        logger.info(
                            "Backfilled attendance event",
                            event_type=log.event_type,
                            user=message.author.name,
                            time=message.created_at,
                        )
                    else:
                        skipped += 1

                except Exception as e:
                    logger.error(
                        "Error processing historical message",
                        error=str(e),
                        message_id=message.id,
                    )
                    skipped += 1

            await db.commit()

        # Send summary
        embed = discord.Embed(
            title="✅ Attendance Sync Complete",
            color=discord.Color.green(),
        )
        embed.add_field(name="Events Imported", value=str(processed), inline=True)
        embed.add_field(name="Messages Skipped", value=str(skipped), inline=True)
        embed.add_field(
            name="Period",
            value=f"Today ({today_start.strftime('%Y-%m-%d')})",
            inline=False,
        )

        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="attendance-status", description="Show current team attendance status")
    async def show_status(self, interaction: discord.Interaction) -> None:
        """Show current attendance status for the team."""
        await interaction.response.defer()

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild_id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "No tenant found for this server.",
                    ephemeral=True,
                )
                return

            service = AttendanceService(db)
            team_status = await service.get_team_status(tenant.id)

        if not team_status:
            await interaction.followup.send(
                "No attendance data yet. Team members should post in #checkin-status.",
            )
            return

        # Build embed
        embed = discord.Embed(
            title="📊 Team Attendance Status",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        # Group by status
        active = []
        on_break = []
        offline = []

        for user in team_status:
            name = user.get("discord_username") or "Unknown"
            status = user.get("status", "unknown")

            if status == "active":
                checkin = user.get("today_stats", {}).get("checkin_at")
                if checkin:
                    time_str = checkin.strftime("%I:%M %p")
                    active.append(f"**{name}** (since {time_str})")
                else:
                    active.append(f"**{name}**")

            elif status == "on_break":
                reason = user.get("current_break_reason") or "break"
                expected = user.get("expected_return_at")
                if expected:
                    time_str = expected.strftime("%I:%M %p")
                    on_break.append(f"**{name}** - {reason} (back ~{time_str})")
                else:
                    on_break.append(f"**{name}** - {reason}")

            else:
                last_checkout = user.get("last_checkout_at")
                if last_checkout:
                    time_str = last_checkout.strftime("%I:%M %p")
                    offline.append(f"**{name}** (last: {time_str})")
                else:
                    offline.append(f"**{name}**")

        if active:
            embed.add_field(
                name=f"🟢 Active ({len(active)})",
                value="\n".join(active) or "None",
                inline=False,
            )

        if on_break:
            embed.add_field(
                name=f"🟡 On Break ({len(on_break)})",
                value="\n".join(on_break) or "None",
                inline=False,
            )

        if offline:
            embed.add_field(
                name=f"⚫ Offline ({len(offline)})",
                value="\n".join(offline) or "None",
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the AttendanceCog."""
    await bot.add_cog(AttendanceCog(bot))
