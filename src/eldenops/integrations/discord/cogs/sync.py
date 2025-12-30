"""Sync commands for fetching historical Discord data."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.config.constants import DiscordEventType
from eldenops.db.engine import get_session
from eldenops.db.models.discord import DiscordEvent, MonitoredChannel
from eldenops.db.models.tenant import Tenant
from eldenops.db.models.user import User
from eldenops.db.models.project import Project, TenantProjectConfig

logger = structlog.get_logger()


class SyncCog(commands.Cog):
    """Commands for syncing historical Discord data and project configuration."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._syncing: dict[int, bool] = {}  # guild_id -> is_syncing

    sync_group = app_commands.Group(name="sync", description="Sync historical data")
    projects_group = app_commands.Group(name="projects", description="Project configuration")

    # Thread naming pattern detection regexes
    COMMON_PATTERNS = [
        (r"^(.+?)\s*\((.+?)\)$", "{member} ({project})"),  # "Jeo (CUA-BOT)"
        (r"^(.+?)\s*-\s*(.+?)$", "{project} - {member}"),  # "CUA-BOT - Jeo"
        (r"^(.+?)$", "{project}"),  # Just project name
    ]

    @projects_group.command(name="analyze", description="AI analyzes your Discord and auto-configures EldenOps")
    @app_commands.checks.has_permissions(administrator=True)
    async def projects_analyze(self, interaction: discord.Interaction) -> None:
        """Analyze Discord server structure and auto-configure project tracking."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Create analysis embed
        embed = discord.Embed(
            title="Analyzing Discord Server...",
            description="Scanning channels, threads, and roles to auto-configure EldenOps",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Status", value="Scanning channels...", inline=False)
        status_message = await interaction.followup.send(embed=embed)

        analysis = {
            "channels_with_threads": [],
            "detected_pattern": None,
            "sample_threads": [],
            "stakeholder_roles": [],
            "team_roles": [],
            "total_threads": 0,
        }

        # Scan all text channels for threads
        for channel in interaction.guild.text_channels:
            threads = list(channel.threads)

            # Also check archived threads
            try:
                async for thread in channel.archived_threads(limit=50):
                    threads.append(thread)
            except discord.Forbidden:
                pass

            if threads:
                analysis["channels_with_threads"].append({
                    "channel": channel,
                    "thread_count": len(threads),
                    "threads": threads[:10],  # Sample first 10
                })
                analysis["total_threads"] += len(threads)
                analysis["sample_threads"].extend([t.name for t in threads[:5]])

        # Update status
        embed.set_field_at(0, name="Status", value="Analyzing thread patterns...", inline=False)
        await status_message.edit(embed=embed)

        # Detect thread naming pattern
        if analysis["sample_threads"]:
            pattern_scores = {}
            for thread_name in analysis["sample_threads"][:20]:
                for regex, pattern in self.COMMON_PATTERNS:
                    if re.match(regex, thread_name):
                        pattern_scores[pattern] = pattern_scores.get(pattern, 0) + 1
                        break

            if pattern_scores:
                analysis["detected_pattern"] = max(pattern_scores, key=pattern_scores.get)

        # Analyze roles for stakeholder vs team member classification
        embed.set_field_at(0, name="Status", value="Analyzing roles...", inline=False)
        await status_message.edit(embed=embed)

        # Stakeholder/leadership roles - get high-level reports
        stakeholder_keywords = [
            "stakeholder", "client", "owner", "manager", "lead", "director",
            "exec", "ceo", "cto", "cfo", "coo", "founder", "co-founder", "cofounder",
            "president", "vp", "vice president", "head", "chief", "principal",
            "investor", "board", "advisor", "supervisor", "boss", "admin", "administrator",
            "moderator", "mod", "staff", "management", "leadership", "senior"
        ]
        # Team/contributor roles - get detailed metrics
        team_keywords = [
            "dev", "devs", "developer", "engineer", "engineering", "programmer", "coder",
            "frontend", "backend", "fullstack", "full-stack", "software", "swe",
            "designer", "ui", "ux", "graphic", "creative",
            "qa", "tester", "testing", "quality",
            "team", "member", "contributor", "intern", "junior", "mid", "associate",
            "analyst", "specialist", "technician", "support", "ops", "devops", "sre",
            "data", "ml", "ai", "scientist", "researcher",
            "writer", "content", "marketing", "community"
        ]

        for role in interaction.guild.roles:
            role_name_lower = role.name.lower()
            if any(kw in role_name_lower for kw in stakeholder_keywords):
                analysis["stakeholder_roles"].append(role)
            elif any(kw in role_name_lower for kw in team_keywords):
                analysis["team_roles"].append(role)

        # Find best task-delegation channel candidate
        best_channel = None
        if analysis["channels_with_threads"]:
            # Sort by thread count, prefer channels with "task", "delegation", "project" in name
            def channel_score(item):
                score = item["thread_count"]
                name_lower = item["channel"].name.lower()
                if "task" in name_lower or "delegation" in name_lower:
                    score += 100
                if "project" in name_lower:
                    score += 50
                return score

            analysis["channels_with_threads"].sort(key=channel_score, reverse=True)
            best_channel = analysis["channels_with_threads"][0]

        # Build analysis results embed
        embed.title = "Discord Analysis Complete"
        embed.description = "Here's what I found in your server:"
        embed.color = discord.Color.green()
        embed.clear_fields()

        # Channels with threads
        if analysis["channels_with_threads"]:
            channel_list = "\n".join([
                f"• #{c['channel'].name} ({c['thread_count']} threads)"
                for c in analysis["channels_with_threads"][:5]
            ])
            embed.add_field(
                name=f"Channels with Threads ({len(analysis['channels_with_threads'])})",
                value=channel_list,
                inline=False,
            )

            if best_channel:
                embed.add_field(
                    name="Recommended Task Channel",
                    value=f"#{best_channel['channel'].name} (most active with {best_channel['thread_count']} threads)",
                    inline=False,
                )

        # Detected pattern
        if analysis["detected_pattern"]:
            examples = {
                "{member} ({project})": "e.g., 'Jeo (CUA-BOT)'",
                "{project} - {member}": "e.g., 'CUA-BOT - Jeo'",
                "{project}": "e.g., 'CUA-BOT'",
            }
            embed.add_field(
                name="Detected Thread Pattern",
                value=f"`{analysis['detected_pattern']}`\n{examples.get(analysis['detected_pattern'], '')}",
                inline=False,
            )

            # Show sample threads
            if analysis["sample_threads"][:3]:
                samples = "\n".join([f"• {t}" for t in analysis["sample_threads"][:3]])
                embed.add_field(
                    name="Sample Threads Found",
                    value=samples,
                    inline=False,
                )

        # Role analysis
        role_info = []
        if analysis["stakeholder_roles"]:
            role_info.append(f"**Stakeholder roles:** {', '.join([r.name for r in analysis['stakeholder_roles'][:3]])}")
        if analysis["team_roles"]:
            role_info.append(f"**Team roles:** {', '.join([r.name for r in analysis['team_roles'][:3]])}")

        if role_info:
            embed.add_field(
                name="Detected Roles",
                value="\n".join(role_info),
                inline=False,
            )

        await status_message.edit(embed=embed)

        # If we have enough info, offer to auto-configure
        if best_channel and analysis["detected_pattern"]:
            # Auto-configure
            async with get_session() as db:
                # Get tenant
                tenant_result = await db.execute(
                    select(Tenant).where(
                        Tenant.discord_guild_id == interaction.guild.id,
                        Tenant.is_active == True,
                    )
                )
                tenant = tenant_result.scalar_one_or_none()

                if tenant:
                    # Get or create config
                    config_result = await db.execute(
                        select(TenantProjectConfig).where(
                            TenantProjectConfig.tenant_id == tenant.id
                        )
                    )
                    config = config_result.scalar_one_or_none()

                    if not config:
                        config = TenantProjectConfig(tenant_id=tenant.id)
                        db.add(config)

                    # Update config with detected settings
                    config.task_channel_id = best_channel["channel"].id
                    config.task_channel_name = best_channel["channel"].name
                    config.thread_name_pattern = analysis["detected_pattern"]
                    config.auto_create_projects = True

                    # Configure role-based report access
                    stakeholder_role_ids = [r.id for r in analysis["stakeholder_roles"]]
                    team_role_ids = [r.id for r in analysis["team_roles"]]

                    config.report_config = {
                        "stakeholder_roles": stakeholder_role_ids,
                        "team_roles": team_role_ids,
                        "stakeholder_reports": {
                            "types": ["weekly_summary", "monthly_summary", "project_status"],
                            "metrics": ["completion_rate", "blockers", "milestones", "budget_status"],
                            "detail_level": "high_level",
                        },
                        "team_reports": {
                            "types": ["daily_standup", "sprint_review", "individual_metrics"],
                            "metrics": ["commits", "prs", "code_reviews", "messages", "voice_time"],
                            "detail_level": "detailed",
                        },
                    }

                    config.ai_config = {
                        "analyze_frequency": "daily",
                        "suggestion_types": ["blockers", "next_steps", "risks", "kudos"],
                        "context_window_days": 30,
                        "personalize_by_role": True,
                    }

                    await db.commit()

                    logger.info(
                        "Auto-configured project settings",
                        guild_id=interaction.guild.id,
                        channel=best_channel["channel"].name,
                        pattern=analysis["detected_pattern"],
                    )

            # Send confirmation
            config_embed = discord.Embed(
                title="Auto-Configuration Applied",
                description="EldenOps has been configured based on your Discord structure!",
                color=discord.Color.gold(),
            )
            config_embed.add_field(
                name="Task Channel",
                value=f"#{best_channel['channel'].name}",
                inline=True,
            )
            config_embed.add_field(
                name="Thread Pattern",
                value=f"`{analysis['detected_pattern']}`",
                inline=True,
            )
            config_embed.add_field(
                name="Auto-create Projects",
                value="Enabled",
                inline=True,
            )

            # Report configuration summary
            report_summary = []
            if analysis["stakeholder_roles"]:
                report_summary.append(
                    f"**Stakeholders** ({', '.join([r.name for r in analysis['stakeholder_roles'][:2]])}): "
                    "High-level summaries, project status, blockers"
                )
            if analysis["team_roles"]:
                report_summary.append(
                    f"**Team Members** ({', '.join([r.name for r in analysis['team_roles'][:2]])}): "
                    "Detailed metrics, commits, PRs, daily standups"
                )

            if report_summary:
                config_embed.add_field(
                    name="Role-Based Reports",
                    value="\n".join(report_summary),
                    inline=False,
                )
            else:
                config_embed.add_field(
                    name="Role-Based Reports",
                    value="No specific roles detected. All users will see full reports.\nTip: Create roles with 'stakeholder' or 'team' in the name for personalized reports.",
                    inline=False,
                )

            config_embed.add_field(
                name="Next Steps",
                value="1. Run `/sync threads` to import existing threads as projects\n"
                      "2. Run `/sync history` to sync message history for insights\n"
                      "3. View reports at your dashboard",
                inline=False,
            )

            await interaction.followup.send(embed=config_embed)

        else:
            # Not enough info to auto-configure
            help_embed = discord.Embed(
                title="Manual Configuration Needed",
                description="I couldn't detect enough structure to auto-configure. Please set up manually:",
                color=discord.Color.orange(),
            )
            help_embed.add_field(
                name="Command",
                value="`/projects setup channel:#your-task-channel pattern:{member} ({project})`",
                inline=False,
            )

            if not analysis["channels_with_threads"]:
                help_embed.add_field(
                    name="Tip",
                    value="Create a task-delegation channel with threads for each project/task assignment.",
                    inline=False,
                )

            await interaction.followup.send(embed=help_embed)

    @sync_group.command(name="history", description="Sync historical message data from channels")
    @app_commands.describe(
        days="How far back to sync (7, 30, 90, 365, or 0 for all history)",
        channel="Specific channel to sync (leave empty for all monitored channels)",
    )
    @app_commands.choices(
        days=[
            app_commands.Choice(name="7 days", value=7),
            app_commands.Choice(name="30 days", value=30),
            app_commands.Choice(name="90 days", value=90),
            app_commands.Choice(name="365 days (1 year)", value=365),
            app_commands.Choice(name="All history", value=0),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_history(
        self,
        interaction: discord.Interaction,
        days: int,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Sync historical message metadata from Discord channels."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        # Check if already syncing for this guild
        if self._syncing.get(interaction.guild.id):
            await interaction.response.send_message(
                "A sync is already in progress for this server. Please wait.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "This server is not set up with EldenOps yet. Use `/setup` first.",
                    ephemeral=True,
                )
                return

            # Get channels to sync
            if channel:
                # Check if channel is monitored
                monitored_result = await db.execute(
                    select(MonitoredChannel).where(
                        MonitoredChannel.tenant_id == tenant.id,
                        MonitoredChannel.channel_id == channel.id,
                        MonitoredChannel.is_active == True,
                    )
                )
                monitored = monitored_result.scalar_one_or_none()
                if not monitored:
                    await interaction.followup.send(
                        f"#{channel.name} is not a monitored channel. "
                        "Add it with `/config channels add` first.",
                        ephemeral=True,
                    )
                    return
                channels_to_sync = [channel]
            else:
                # Get all monitored channels
                monitored_result = await db.execute(
                    select(MonitoredChannel).where(
                        MonitoredChannel.tenant_id == tenant.id,
                        MonitoredChannel.is_active == True,
                    )
                )
                monitored_channels = monitored_result.scalars().all()

                if not monitored_channels:
                    await interaction.followup.send(
                        "No monitored channels found. Add channels with `/config channels add` first.",
                        ephemeral=True,
                    )
                    return

                channels_to_sync = []
                for mc in monitored_channels:
                    ch = interaction.guild.get_channel(mc.channel_id)
                    if ch and isinstance(ch, discord.TextChannel):
                        channels_to_sync.append(ch)

            if not channels_to_sync:
                await interaction.followup.send(
                    "No valid text channels found to sync.", ephemeral=True
                )
                return

        # Calculate time range
        after_date = None
        if days > 0:
            after_date = datetime.now(timezone.utc) - timedelta(days=days)
            time_desc = f"last {days} days"
        else:
            time_desc = "all history"

        # Create initial status embed
        embed = discord.Embed(
            title="Syncing Historical Messages",
            description=f"Syncing {time_desc} from {len(channels_to_sync)} channel(s)...",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Status", value="Starting...", inline=False)
        embed.add_field(name="Progress", value="0 messages processed", inline=True)
        embed.add_field(name="Channels", value=f"0/{len(channels_to_sync)}", inline=True)

        status_message = await interaction.followup.send(embed=embed)

        # Start sync in background
        self._syncing[interaction.guild.id] = True
        try:
            total_messages = 0
            total_new = 0
            channels_done = 0

            for ch in channels_to_sync:
                try:
                    messages_in_channel, new_in_channel = await self._sync_channel(
                        ch, tenant.id, after_date, status_message, embed,
                        total_messages, channels_done, len(channels_to_sync)
                    )
                    total_messages += messages_in_channel
                    total_new += new_in_channel
                    channels_done += 1

                    # Update progress
                    embed.set_field_at(
                        0, name="Status",
                        value=f"Completed #{ch.name}", inline=False
                    )
                    embed.set_field_at(
                        1, name="Progress",
                        value=f"{total_messages:,} messages processed ({total_new:,} new)",
                        inline=True,
                    )
                    embed.set_field_at(
                        2, name="Channels",
                        value=f"{channels_done}/{len(channels_to_sync)}",
                        inline=True,
                    )
                    await status_message.edit(embed=embed)

                except discord.Forbidden:
                    logger.warning(
                        "No permission to read channel history",
                        channel_id=ch.id,
                        channel_name=ch.name,
                    )
                except Exception as e:
                    logger.error(
                        "Error syncing channel",
                        channel_id=ch.id,
                        error=str(e),
                    )

            # Final status
            embed.title = "Sync Complete"
            embed.color = discord.Color.green()
            embed.description = f"Successfully synced {time_desc}"
            embed.set_field_at(
                0, name="Status", value="Done!", inline=False
            )
            embed.set_field_at(
                1, name="Total Messages",
                value=f"{total_messages:,} processed ({total_new:,} new)",
                inline=True,
            )
            embed.set_field_at(
                2, name="Channels",
                value=f"{channels_done}/{len(channels_to_sync)} completed",
                inline=True,
            )
            embed.timestamp = datetime.now(timezone.utc)
            await status_message.edit(embed=embed)

            logger.info(
                "History sync complete",
                guild_id=interaction.guild.id,
                total_messages=total_messages,
                new_messages=total_new,
                channels=channels_done,
            )

        finally:
            self._syncing[interaction.guild.id] = False

    async def _sync_channel(
        self,
        channel: discord.TextChannel,
        tenant_id: str,
        after_date: Optional[datetime],
        status_message: discord.Message,
        embed: discord.Embed,
        current_total: int,
        channels_done: int,
        total_channels: int,
    ) -> tuple[int, int]:
        """Sync messages from a single channel.

        Returns tuple of (total_messages_processed, new_messages_added).
        """
        messages_processed = 0
        new_messages = 0
        batch_size = 100
        last_update = datetime.now(timezone.utc)
        update_interval = timedelta(seconds=3)  # Update status every 3 seconds

        async with get_session() as db:
            # Get existing message IDs to avoid duplicates
            existing_result = await db.execute(
                select(DiscordEvent.message_id).where(
                    DiscordEvent.tenant_id == tenant_id,
                    DiscordEvent.channel_id == channel.id,
                    DiscordEvent.message_id.isnot(None),
                )
            )
            existing_ids = {row[0] for row in existing_result.fetchall()}

            # Fetch messages
            async for message in channel.history(limit=None, after=after_date, oldest_first=True):
                if message.author.bot:
                    continue

                messages_processed += 1

                # Skip if already exists
                if message.id in existing_ids:
                    continue

                # Get or create user
                user_result = await db.execute(
                    select(User).where(User.discord_id == message.author.id)
                )
                user = user_result.scalar_one_or_none()
                user_id = user.id if user else None

                # Create event record
                event = DiscordEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    event_type=DiscordEventType.MESSAGE,
                    channel_id=channel.id,
                    message_id=message.id,
                    word_count=len(message.content.split()) if message.content else 0,
                    has_attachments=len(message.attachments) > 0,
                    has_links="http" in message.content.lower() if message.content else False,
                    has_mentions=len(message.mentions) > 0 or len(message.role_mentions) > 0,
                    is_reply=message.reference is not None,
                    thread_id=message.channel.id if isinstance(message.channel, discord.Thread) else None,
                    event_metadata={"discord_user_id": message.author.id, "synced": True},
                    created_at=message.created_at,
                )
                db.add(event)
                new_messages += 1

                # Commit in batches
                if new_messages % batch_size == 0:
                    await db.commit()

                # Update status periodically
                now = datetime.now(timezone.utc)
                if now - last_update > update_interval:
                    embed.set_field_at(
                        0, name="Status",
                        value=f"Syncing #{channel.name}...",
                        inline=False,
                    )
                    embed.set_field_at(
                        1, name="Progress",
                        value=f"{current_total + messages_processed:,} messages ({new_messages:,} new in this channel)",
                        inline=True,
                    )
                    try:
                        await status_message.edit(embed=embed)
                    except discord.HTTPException:
                        pass  # Rate limited, skip update
                    last_update = now

                # Small delay to respect rate limits
                if messages_processed % 1000 == 0:
                    await asyncio.sleep(0.1)

            # Final commit
            await db.commit()

        return messages_processed, new_messages

    @sync_group.command(name="threads", description="Sync task delegation threads as projects")
    @app_commands.describe(
        auto_create="Automatically create projects for unlinked threads",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_threads(
        self,
        interaction: discord.Interaction,
        auto_create: bool = True,
    ) -> None:
        """Scan task delegation channel and sync threads as projects."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "This server is not set up with EldenOps yet. Use `/setup` first.",
                    ephemeral=True,
                )
                return

            # Get project config
            config_result = await db.execute(
                select(TenantProjectConfig).where(
                    TenantProjectConfig.tenant_id == tenant.id
                )
            )
            config = config_result.scalar_one_or_none()

            if not config or not config.task_channel_id:
                await interaction.followup.send(
                    "No task delegation channel configured. "
                    "Set one up in the Projects Configuration page on the dashboard.",
                    ephemeral=True,
                )
                return

            # Get the task delegation channel
            task_channel = interaction.guild.get_channel(config.task_channel_id)
            if not task_channel or not isinstance(task_channel, discord.TextChannel):
                await interaction.followup.send(
                    f"Could not find task delegation channel (ID: {config.task_channel_id}). "
                    "Please update the configuration.",
                    ephemeral=True,
                )
                return

            # Get existing projects to check for duplicates
            projects_result = await db.execute(
                select(Project).where(Project.tenant_id == tenant.id)
            )
            existing_projects = {p.discord_thread_id: p for p in projects_result.scalars().all()}

            # Compile regex pattern from thread name pattern
            pattern = self._compile_thread_pattern(config.thread_name_pattern)

            # Create status embed
            embed = discord.Embed(
                title="Syncing Task Delegation Threads",
                description=f"Scanning #{task_channel.name} for threads...",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Pattern", value=f"`{config.thread_name_pattern}`", inline=False)
            embed.add_field(name="Threads Found", value="0", inline=True)
            embed.add_field(name="Projects Created", value="0", inline=True)
            embed.add_field(name="Already Linked", value="0", inline=True)

            status_message = await interaction.followup.send(embed=embed)

            # Scan threads
            threads_found = 0
            projects_created = 0
            already_linked = 0
            skipped = []

            # Get archived and active threads
            all_threads = list(task_channel.threads)

            # Also fetch archived threads
            try:
                async for thread in task_channel.archived_threads(limit=100):
                    all_threads.append(thread)
            except discord.Forbidden:
                logger.warning("Cannot access archived threads", channel_id=task_channel.id)

            for thread in all_threads:
                threads_found += 1

                # Check if already linked
                if thread.id in existing_projects:
                    already_linked += 1
                    continue

                # Parse thread name
                parsed = self._parse_thread_name(thread.name, pattern, config.thread_name_pattern)
                if not parsed:
                    skipped.append(f"Could not parse: {thread.name}")
                    continue

                project_name, member_name = parsed

                if auto_create:
                    # Create new project
                    project = Project(
                        tenant_id=tenant.id,
                        name=project_name or thread.name,
                        description=f"Auto-created from Discord thread: {thread.name}",
                        discord_thread_id=thread.id,
                        discord_thread_name=thread.name,
                        discord_channel_id=task_channel.id,
                    )
                    db.add(project)
                    projects_created += 1

                    logger.info(
                        "Project auto-created from thread",
                        project_name=project_name,
                        thread_id=thread.id,
                        thread_name=thread.name,
                    )

            await db.commit()

            # Update final status
            embed.title = "Thread Sync Complete"
            embed.color = discord.Color.green()
            embed.description = f"Scanned {threads_found} threads in #{task_channel.name}"
            embed.set_field_at(0, name="Pattern", value=f"`{config.thread_name_pattern}`", inline=False)
            embed.set_field_at(1, name="Threads Found", value=str(threads_found), inline=True)
            embed.set_field_at(2, name="Projects Created", value=str(projects_created), inline=True)
            embed.set_field_at(3, name="Already Linked", value=str(already_linked), inline=True)

            if skipped:
                skipped_text = "\n".join(skipped[:5])
                if len(skipped) > 5:
                    skipped_text += f"\n... and {len(skipped) - 5} more"
                embed.add_field(name="Skipped", value=skipped_text, inline=False)

            embed.timestamp = datetime.now(timezone.utc)
            await status_message.edit(embed=embed)

            logger.info(
                "Thread sync complete",
                guild_id=interaction.guild.id,
                threads_found=threads_found,
                projects_created=projects_created,
                already_linked=already_linked,
            )

    def _compile_thread_pattern(self, pattern: str) -> re.Pattern:
        """Convert thread name pattern to regex.

        Pattern placeholders:
        - {member} -> captured group for member name
        - {project} -> captured group for project name
        """
        # Escape special regex chars, but preserve our placeholders
        escaped = re.escape(pattern)
        # Replace escaped placeholders with capture groups
        regex = escaped.replace(r"\{member\}", r"(?P<member>.+?)")
        regex = regex.replace(r"\{project\}", r"(?P<project>.+?)")
        return re.compile(f"^{regex}$", re.IGNORECASE)

    def _parse_thread_name(
        self,
        thread_name: str,
        pattern: re.Pattern,
        pattern_str: str,
    ) -> Optional[Tuple[Optional[str], Optional[str]]]:
        """Parse thread name using configured pattern.

        Returns (project_name, member_name) or None if no match.
        """
        match = pattern.match(thread_name)
        if not match:
            return None

        groups = match.groupdict()
        project_name = groups.get("project")
        member_name = groups.get("member")

        # If pattern only has {project}, use thread name for project
        if "{project}" in pattern_str and not project_name:
            return None

        return project_name, member_name

    @sync_group.command(name="status", description="Check if a sync is in progress")
    async def sync_status(self, interaction: discord.Interaction) -> None:
        """Check sync status for this server."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        is_syncing = self._syncing.get(interaction.guild.id, False)
        if is_syncing:
            await interaction.response.send_message(
                "A sync is currently in progress. Check the status message for updates.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "No sync is currently running.", ephemeral=True
            )

    # ============ Project Configuration Commands ============

    @projects_group.command(name="config", description="View current project configuration")
    async def projects_config(self, interaction: discord.Interaction) -> None:
        """Show current project configuration."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.response.send_message(
                    "This server is not set up with EldenOps yet.", ephemeral=True
                )
                return

            # Get config
            config_result = await db.execute(
                select(TenantProjectConfig).where(
                    TenantProjectConfig.tenant_id == tenant.id
                )
            )
            config = config_result.scalar_one_or_none()

            embed = discord.Embed(
                title="Project Configuration",
                color=discord.Color.blue(),
            )

            if config:
                # Task channel
                if config.task_channel_id:
                    channel = interaction.guild.get_channel(config.task_channel_id)
                    channel_name = f"#{channel.name}" if channel else f"ID: {config.task_channel_id}"
                    embed.add_field(
                        name="Task Delegation Channel",
                        value=channel_name,
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Task Delegation Channel",
                        value="Not configured",
                        inline=False,
                    )

                embed.add_field(
                    name="Thread Name Pattern",
                    value=f"`{config.thread_name_pattern}`",
                    inline=False,
                )
                embed.add_field(
                    name="Auto-create Projects",
                    value="Enabled" if config.auto_create_projects else "Disabled",
                    inline=True,
                )

                # Show example
                examples = {
                    "{member} ({project})": "Jeo (CUA-BOT)",
                    "{project} - {member}": "CUA-BOT - Jeo",
                    "{project}": "CUA-BOT",
                    "{member}": "Jeo",
                }
                example = examples.get(config.thread_name_pattern, "Custom pattern")
                embed.add_field(
                    name="Example Thread Name",
                    value=f"`{example}`",
                    inline=True,
                )
            else:
                embed.description = "No project configuration set up yet.\n\nUse `/projects setup` to configure."

            embed.set_footer(text="Use /projects setup to change settings")
            await interaction.response.send_message(embed=embed)

    @projects_group.command(name="setup", description="Set up project tracking configuration")
    @app_commands.describe(
        channel="The task delegation channel containing project threads",
        pattern="Thread naming pattern: {member} ({project}), {project} - {member}, {project}, or {member}",
        auto_create="Automatically create projects from new threads",
    )
    @app_commands.choices(
        pattern=[
            app_commands.Choice(name="{member} ({project}) - e.g., 'Jeo (CUA-BOT)'", value="{member} ({project})"),
            app_commands.Choice(name="{project} - {member} - e.g., 'CUA-BOT - Jeo'", value="{project} - {member}"),
            app_commands.Choice(name="{project} - e.g., 'CUA-BOT'", value="{project}"),
            app_commands.Choice(name="{member} - e.g., 'Jeo'", value="{member}"),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def projects_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        pattern: str = "{member} ({project})",
        auto_create: bool = True,
    ) -> None:
        """Configure project tracking for this server."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "This server is not set up with EldenOps yet. Use `/setup` first.",
                    ephemeral=True,
                )
                return

            # Get or create config
            config_result = await db.execute(
                select(TenantProjectConfig).where(
                    TenantProjectConfig.tenant_id == tenant.id
                )
            )
            config = config_result.scalar_one_or_none()

            if not config:
                config = TenantProjectConfig(tenant_id=tenant.id)
                db.add(config)

            # Update config
            config.task_channel_id = channel.id
            config.task_channel_name = channel.name
            config.thread_name_pattern = pattern
            config.auto_create_projects = auto_create

            await db.commit()

            logger.info(
                "Project config updated",
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                pattern=pattern,
            )

        # Show confirmation
        embed = discord.Embed(
            title="Project Configuration Updated",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Task Delegation Channel",
            value=f"#{channel.name}",
            inline=False,
        )
        embed.add_field(
            name="Thread Name Pattern",
            value=f"`{pattern}`",
            inline=True,
        )
        embed.add_field(
            name="Auto-create Projects",
            value="Enabled" if auto_create else "Disabled",
            inline=True,
        )

        # Show example
        examples = {
            "{member} ({project})": "Jeo (CUA-BOT)",
            "{project} - {member}": "CUA-BOT - Jeo",
            "{project}": "CUA-BOT",
            "{member}": "Jeo",
        }
        example = examples.get(pattern, "Custom")
        embed.add_field(
            name="Example Thread Name",
            value=f"`{example}`",
            inline=False,
        )

        embed.set_footer(text="Run /sync threads to sync existing threads as projects")
        await interaction.followup.send(embed=embed)

    @projects_group.command(name="list", description="List all projects")
    async def projects_list(self, interaction: discord.Interaction) -> None:
        """List all projects for this server."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.discord_guild_id == interaction.guild.id,
                    Tenant.is_active == True,
                )
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.response.send_message(
                    "This server is not set up with EldenOps yet.", ephemeral=True
                )
                return

            # Get projects
            projects_result = await db.execute(
                select(Project).where(Project.tenant_id == tenant.id)
            )
            projects = projects_result.scalars().all()

            if not projects:
                await interaction.response.send_message(
                    "No projects found. Use `/projects setup` to configure, "
                    "then `/sync threads` to sync existing threads.",
                    ephemeral=True,
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"Projects ({len(projects)})",
                color=discord.Color.blue(),
            )

            status_emoji = {
                "planning": "📋",
                "active": "🟢",
                "on_hold": "🟡",
                "blocked": "🔴",
                "completed": "✅",
                "archived": "📦",
            }

            for project in projects[:25]:  # Discord embed limit
                emoji = status_emoji.get(project.status, "📁")
                thread_info = ""
                if project.discord_thread_id:
                    thread = interaction.guild.get_thread(project.discord_thread_id)
                    if thread:
                        thread_info = f" → <#{thread.id}>"

                embed.add_field(
                    name=f"{emoji} {project.name}",
                    value=f"Status: {project.status.replace('_', ' ').title()}{thread_info}",
                    inline=True,
                )

            if len(projects) > 25:
                embed.set_footer(text=f"Showing 25 of {len(projects)} projects")

            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the SyncCog."""
    await bot.add_cog(SyncCog(bot))
