"""Report generation and scheduling commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, func
import structlog

from eldenops.ai.router import analyze_with_ai
from eldenops.config.constants import ReportType
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant
from eldenops.db.models.discord import DiscordEvent, VoiceSession
from eldenops.db.models.github import GitHubEvent
from eldenops.db.models.report import ReportConfig, Report

logger = structlog.get_logger()


async def get_tenant_for_guild(guild_id: int, db) -> Optional[Tenant]:
    """Helper to get tenant for a guild."""
    result = await db.execute(
        select(Tenant).where(
            Tenant.discord_guild_id == guild_id,
            Tenant.is_active == True,
        )
    )
    return result.scalar_one_or_none()


class ReportsCog(commands.Cog, name="Reports"):
    """Report generation and scheduling commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    report_group = app_commands.Group(
        name="report",
        description="Generate and manage reports",
        default_permissions=discord.Permissions(administrator=True),
    )

    @report_group.command(name="generate", description="Generate an on-demand report")
    @app_commands.describe(
        report_type="Type of report to generate",
        days="Number of days to include (default: 7)",
        channel="Channel to post the report (default: current channel)",
    )
    @app_commands.choices(
        report_type=[
            app_commands.Choice(name="Daily Summary", value="daily_summary"),
            app_commands.Choice(name="Weekly Digest", value="weekly_digest"),
            app_commands.Choice(name="Project Status", value="project_status"),
            app_commands.Choice(name="Team Activity", value="team_activity"),
        ]
    )
    async def generate(
        self,
        interaction: discord.Interaction,
        report_type: str = "weekly_digest",
        days: int = 7,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Generate a report on demand."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        target_channel = channel or interaction.channel

        await interaction.response.defer()

        logger.info(
            "Generating report",
            guild_id=interaction.guild.id,
            report_type=report_type,
            days=days,
            user_id=interaction.user.id,
        )

        # Generate actual report using database and AI
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.")
                return

            since = datetime.now(timezone.utc) - timedelta(days=days)

            # Get Discord stats
            discord_stats = await db.execute(
                select(
                    func.count(DiscordEvent.id).label("total_messages"),
                    func.count(func.distinct(DiscordEvent.user_id)).label("active_members"),
                    func.sum(DiscordEvent.word_count).label("total_words"),
                )
                .where(
                    DiscordEvent.tenant_id == tenant.id,
                    DiscordEvent.created_at >= since,
                )
            )
            discord_data = discord_stats.one()

            # Get voice hours
            voice_stats = await db.execute(
                select(func.sum(VoiceSession.duration_seconds))
                .where(
                    VoiceSession.tenant_id == tenant.id,
                    VoiceSession.started_at >= since,
                )
            )
            total_voice_seconds = voice_stats.scalar() or 0
            voice_hours = round(total_voice_seconds / 3600, 1)

            # Get GitHub stats
            github_stats = await db.execute(
                select(
                    func.count(GitHubEvent.id).label("total_events"),
                    func.count(func.distinct(GitHubEvent.github_user_login)).label("contributors"),
                )
                .where(
                    GitHubEvent.tenant_id == tenant.id,
                    GitHubEvent.created_at >= since,
                )
            )
            github_data = github_stats.one()

            # Count by event type
            commit_count = await db.execute(
                select(func.count(GitHubEvent.id))
                .where(
                    GitHubEvent.tenant_id == tenant.id,
                    GitHubEvent.event_type == "commit",
                    GitHubEvent.created_at >= since,
                )
            )
            commits = commit_count.scalar() or 0

            pr_count = await db.execute(
                select(func.count(GitHubEvent.id))
                .where(
                    GitHubEvent.tenant_id == tenant.id,
                    GitHubEvent.event_type == "pull_request",
                    GitHubEvent.created_at >= since,
                )
            )
            prs = pr_count.scalar() or 0

        # Build embed with actual data
        embed = discord.Embed(
            title=f"Report: {report_type.replace('_', ' ').title()}",
            description=f"Analysis of the last {days} days",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Discord Activity",
            value=(
                f"**Messages:** {discord_data.total_messages or 0:,}\n"
                f"**Active Members:** {discord_data.active_members or 0}\n"
                f"**Voice Hours:** {voice_hours}h"
            ),
            inline=True,
        )

        embed.add_field(
            name="GitHub Activity",
            value=(
                f"**Commits:** {commits:,}\n"
                f"**Pull Requests:** {prs:,}\n"
                f"**Contributors:** {github_data.contributors or 0}"
            ),
            inline=True,
        )

        # Generate AI summary if we have data
        if discord_data.total_messages or github_data.total_events:
            try:
                summary_prompt = f"""
                Generate a brief team activity summary for the past {days} days:

                Discord: {discord_data.total_messages or 0} messages, {discord_data.active_members or 0} active members, {voice_hours}h voice
                GitHub: {commits} commits, {prs} PRs, {github_data.contributors or 0} contributors

                Provide 2-3 sentences highlighting key activity and engagement.
                """
                ai_response = await analyze_with_ai(
                    prompt=summary_prompt,
                    system_prompt="You are a concise team analytics assistant. Keep responses brief and actionable.",
                    max_tokens=200,
                    temperature=0.5,
                )
                embed.add_field(
                    name="AI Summary",
                    value=ai_response.content,
                    inline=False,
                )
            except Exception as e:
                logger.error("AI summary generation failed", error=str(e))
                embed.add_field(
                    name="AI Summary",
                    value="_Summary generation unavailable_",
                    inline=False,
                )
        else:
            embed.add_field(
                name="AI Summary",
                value=(
                    "_No data available yet._\n\n"
                    "Configure channels and GitHub repos to start tracking."
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"Report generated by {interaction.user.display_name}"
        )

        await interaction.followup.send(embed=embed)

    @report_group.command(name="schedule", description="Set up scheduled reports")
    @app_commands.describe(
        schedule="When to send reports",
        channel="Channel to post reports",
        report_type="Type of report",
    )
    @app_commands.choices(
        schedule=[
            app_commands.Choice(name="Daily (9 AM)", value="daily_9am"),
            app_commands.Choice(name="Daily (6 PM)", value="daily_6pm"),
            app_commands.Choice(name="Weekly (Monday 9 AM)", value="weekly_monday"),
            app_commands.Choice(name="Weekly (Friday 5 PM)", value="weekly_friday"),
        ],
        report_type=[
            app_commands.Choice(name="Daily Summary", value="daily_summary"),
            app_commands.Choice(name="Weekly Digest", value="weekly_digest"),
            app_commands.Choice(name="Project Status", value="project_status"),
        ],
    )
    async def schedule(
        self,
        interaction: discord.Interaction,
        schedule: str,
        channel: discord.TextChannel,
        report_type: str = "weekly_digest",
    ) -> None:
        """Schedule automated reports."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Convert schedule choice to cron expression
        cron_map = {
            "daily_9am": "0 9 * * *",
            "daily_6pm": "0 18 * * *",
            "weekly_monday": "0 9 * * 1",
            "weekly_friday": "0 17 * * 5",
        }
        cron = cron_map.get(schedule, "0 9 * * 1")

        logger.info(
            "Scheduling report",
            guild_id=interaction.guild.id,
            schedule=schedule,
            cron=cron,
            channel_id=channel.id,
            report_type=report_type,
        )

        # Save schedule to database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            # Create report config
            config = ReportConfig(
                tenant_id=tenant.id,
                name=f"{report_type.replace('_', ' ').title()} - {schedule}",
                report_type=report_type,
                schedule_cron=cron,
                delivery_channel_id=channel.id,
                is_active=True,
            )
            db.add(config)

        schedule_display = {
            "daily_9am": "Daily at 9:00 AM",
            "daily_6pm": "Daily at 6:00 PM",
            "weekly_monday": "Every Monday at 9:00 AM",
            "weekly_friday": "Every Friday at 5:00 PM",
        }

        embed = discord.Embed(
            title="Report Scheduled",
            description=f"Scheduled **{report_type.replace('_', ' ').title()}** reports",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Schedule",
            value=schedule_display.get(schedule, schedule),
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=channel.mention,
            inline=True,
        )
        embed.add_field(
            name="Report Type",
            value=report_type.replace("_", " ").title(),
            inline=True,
        )
        embed.set_footer(text="Times are in UTC")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @report_group.command(name="list", description="List scheduled reports")
    async def list_schedules(self, interaction: discord.Interaction) -> None:
        """List all scheduled reports."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch from database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            result = await db.execute(
                select(ReportConfig).where(
                    ReportConfig.tenant_id == tenant.id,
                    ReportConfig.is_active == True,
                    ReportConfig.schedule_cron != None,
                )
            )
            schedules = result.scalars().all()

        embed = discord.Embed(
            title="Scheduled Reports",
            description="Automated reports for this server",
            color=discord.Color.blue(),
        )

        if schedules:
            for sched in schedules:
                channel_mention = f"<#{sched.delivery_channel_id}>" if sched.delivery_channel_id else "Not set"
                embed.add_field(
                    name=f"{sched.name}",
                    value=(
                        f"**Type:** {sched.report_type}\n"
                        f"**Schedule:** `{sched.schedule_cron}`\n"
                        f"**Channel:** {channel_mention}\n"
                        f"**ID:** `{sched.id[:8]}...`"
                    ),
                    inline=False,
                )
        else:
            embed.add_field(
                name="No Scheduled Reports",
                value="Use `/report schedule` to set up automated reports",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @report_group.command(name="cancel", description="Cancel a scheduled report")
    @app_commands.describe(report_id="ID of the scheduled report to cancel")
    async def cancel(
        self,
        interaction: discord.Interaction,
        report_id: str,
    ) -> None:
        """Cancel a scheduled report."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Cancelling scheduled report",
            guild_id=interaction.guild.id,
            report_id=report_id,
        )

        # Delete from database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            # Find report config (match by prefix)
            result = await db.execute(
                select(ReportConfig).where(
                    ReportConfig.tenant_id == tenant.id,
                    ReportConfig.id.startswith(report_id),
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                await interaction.followup.send(f"Report `{report_id}` not found.", ephemeral=True)
                return

            config.is_active = False

        embed = discord.Embed(
            title="Report Cancelled",
            description=f"Scheduled report `{report_id}` has been cancelled",
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Reports cog."""
    cog = ReportsCog(bot)
    bot.tree.add_command(cog.report_group)
    await bot.add_cog(cog)
