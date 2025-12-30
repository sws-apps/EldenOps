"""Configuration commands for channels, GitHub, and AI providers."""

from __future__ import annotations

from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.config.constants import AIProvider, ChannelType
from eldenops.core.security import encrypt_api_key
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant, AIProviderConfig
from eldenops.db.models.discord import MonitoredChannel
from eldenops.db.models.github import GitHubConnection

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


class ConfigCog(commands.Cog, name="Config"):
    """Configuration commands for EldenOps."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Channel configuration group
    channels_group = app_commands.Group(
        name="channels",
        description="Manage monitored channels",
        default_permissions=discord.Permissions(administrator=True),
    )

    @channels_group.command(name="add", description="Add a channel to monitor")
    @app_commands.describe(
        channel="The channel to monitor",
        channel_type="Type of tracking to enable",
    )
    async def channels_add(
        self,
        interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.ForumChannel],
        channel_type: Optional[str] = None,
    ) -> None:
        """Add a channel to the monitoring list."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Determine channel type
        if isinstance(channel, discord.VoiceChannel):
            ch_type = ChannelType.VOICE
        elif isinstance(channel, discord.ForumChannel):
            ch_type = ChannelType.FORUM
        else:
            ch_type = ChannelType.TEXT

        logger.info(
            "Adding monitored channel",
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            channel_name=channel.name,
            channel_type=ch_type,
        )

        # Save to database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            # Check if already monitored
            existing = await db.execute(
                select(MonitoredChannel).where(
                    MonitoredChannel.tenant_id == tenant.id,
                    MonitoredChannel.channel_id == channel.id,
                )
            )
            if existing.scalar_one_or_none():
                await interaction.followup.send(f"{channel.mention} is already being monitored.", ephemeral=True)
                return

            # Add channel
            monitored = MonitoredChannel(
                tenant_id=tenant.id,
                channel_id=channel.id,
                channel_name=channel.name,
                channel_type=ch_type,
            )
            db.add(monitored)

        embed = discord.Embed(
            title="Channel Added",
            description=f"Now monitoring {channel.mention}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Channel Type", value=ch_type, inline=True)
        embed.add_field(name="Channel ID", value=str(channel.id), inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @channels_group.command(name="remove", description="Stop monitoring a channel")
    @app_commands.describe(channel="The channel to stop monitoring")
    async def channels_remove(
        self,
        interaction: discord.Interaction,
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.ForumChannel],
    ) -> None:
        """Remove a channel from monitoring."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Removing monitored channel",
            guild_id=interaction.guild.id,
            channel_id=channel.id,
        )

        # Remove from database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            result = await db.execute(
                select(MonitoredChannel).where(
                    MonitoredChannel.tenant_id == tenant.id,
                    MonitoredChannel.channel_id == channel.id,
                )
            )
            monitored = result.scalar_one_or_none()

            if not monitored:
                await interaction.followup.send(f"{channel.mention} is not being monitored.", ephemeral=True)
                return

            await db.delete(monitored)

        embed = discord.Embed(
            title="Channel Removed",
            description=f"Stopped monitoring {channel.mention}",
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @channels_group.command(name="list", description="List all monitored channels")
    async def channels_list(self, interaction: discord.Interaction) -> None:
        """List all monitored channels."""
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
                select(MonitoredChannel).where(
                    MonitoredChannel.tenant_id == tenant.id,
                    MonitoredChannel.is_active == True,
                )
            )
            channels = result.scalars().all()

        embed = discord.Embed(
            title="Monitored Channels",
            description="Channels being tracked by EldenOps",
            color=discord.Color.blue(),
        )

        # Group by type
        text_channels = [c for c in channels if c.channel_type == ChannelType.TEXT]
        voice_channels = [c for c in channels if c.channel_type == ChannelType.VOICE]
        forum_channels = [c for c in channels if c.channel_type == ChannelType.FORUM]

        if text_channels:
            text_list = "\n".join([f"• <#{c.channel_id}>" for c in text_channels])
            embed.add_field(name="Text Channels", value=text_list, inline=False)
        else:
            embed.add_field(name="Text Channels", value="None", inline=False)

        if voice_channels:
            voice_list = "\n".join([f"• <#{c.channel_id}>" for c in voice_channels])
            embed.add_field(name="Voice Channels", value=voice_list, inline=False)
        else:
            embed.add_field(name="Voice Channels", value="None", inline=False)

        if forum_channels:
            forum_list = "\n".join([f"• <#{c.channel_id}>" for c in forum_channels])
            embed.add_field(name="Forum Channels", value=forum_list, inline=False)

        if not channels:
            embed.add_field(
                name="No Channels",
                value="Use `/config channels add` to start monitoring channels",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # GitHub configuration group
    github_group = app_commands.Group(
        name="github",
        description="Manage GitHub connections",
        default_permissions=discord.Permissions(administrator=True),
    )

    @github_group.command(name="connect", description="Connect a GitHub repository")
    @app_commands.describe(
        repo="Repository in format owner/repo (e.g., myorg/myproject)"
    )
    async def github_connect(
        self,
        interaction: discord.Interaction,
        repo: str,
    ) -> None:
        """Connect a GitHub repository."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Validate repo format
        if "/" not in repo or repo.count("/") != 1:
            await interaction.response.send_message(
                "Invalid repository format. Use `owner/repo` (e.g., `myorg/myproject`)",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        owner, name = repo.split("/")

        logger.info(
            "Connecting GitHub repo",
            guild_id=interaction.guild.id,
            repo=repo,
            user_id=interaction.user.id,
        )

        # Save to database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            # Check if already connected
            existing = await db.execute(
                select(GitHubConnection).where(
                    GitHubConnection.tenant_id == tenant.id,
                    GitHubConnection.repo_full_name == repo,
                )
            )
            if existing.scalar_one_or_none():
                await interaction.followup.send(f"`{repo}` is already connected.", ephemeral=True)
                return

            # Create connection
            connection = GitHubConnection(
                tenant_id=tenant.id,
                org_name=owner,
                repo_name=name,
                repo_full_name=repo,
            )
            db.add(connection)

        embed = discord.Embed(
            title="GitHub Repository Connected",
            description=f"Connected to `{repo}`",
            color=discord.Color.green(),
        )
        embed.add_field(name="Owner", value=owner, inline=True)
        embed.add_field(name="Repository", value=name, inline=True)
        embed.add_field(
            name="Tracking",
            value="Commits, Pull Requests, Issues",
            inline=False,
        )
        embed.set_footer(text="Set up a webhook in your repo to send events to EldenOps")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @github_group.command(name="disconnect", description="Disconnect a GitHub repository")
    @app_commands.describe(repo="Repository to disconnect (owner/repo)")
    async def github_disconnect(
        self,
        interaction: discord.Interaction,
        repo: str,
    ) -> None:
        """Disconnect a GitHub repository."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Disconnecting GitHub repo",
            guild_id=interaction.guild.id,
            repo=repo,
        )

        # Remove from database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            result = await db.execute(
                select(GitHubConnection).where(
                    GitHubConnection.tenant_id == tenant.id,
                    GitHubConnection.repo_full_name == repo,
                )
            )
            connection = result.scalar_one_or_none()

            if not connection:
                await interaction.followup.send(f"`{repo}` is not connected.", ephemeral=True)
                return

            await db.delete(connection)

        embed = discord.Embed(
            title="GitHub Repository Disconnected",
            description=f"Disconnected from `{repo}`",
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @github_group.command(name="list", description="List connected GitHub repositories")
    async def github_list(self, interaction: discord.Interaction) -> None:
        """List connected GitHub repositories."""
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
                select(GitHubConnection).where(
                    GitHubConnection.tenant_id == tenant.id,
                    GitHubConnection.is_active == True,
                )
            )
            connections = result.scalars().all()

        embed = discord.Embed(
            title="Connected GitHub Repositories",
            description="Repositories linked to this server",
            color=discord.Color.blue(),
        )

        if connections:
            repo_list = []
            for conn in connections:
                synced = f"Last synced: {conn.last_synced_at.strftime('%Y-%m-%d')}" if conn.last_synced_at else "Not synced yet"
                repo_list.append(f"• `{conn.repo_full_name}` - {synced}")
            embed.add_field(name="Repositories", value="\n".join(repo_list), inline=False)
        else:
            embed.add_field(
                name="No Repositories Connected",
                value="Use `/config github connect owner/repo` to add one",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # AI configuration group
    ai_group = app_commands.Group(
        name="ai",
        description="Manage AI provider settings",
        default_permissions=discord.Permissions(administrator=True),
    )

    @ai_group.command(name="set", description="Set the AI provider for analysis")
    @app_commands.describe(provider="The AI provider to use")
    @app_commands.choices(
        provider=[
            app_commands.Choice(name="Claude (Anthropic)", value="claude"),
            app_commands.Choice(name="GPT-4 (OpenAI)", value="openai"),
            app_commands.Choice(name="Gemini (Google)", value="gemini"),
            app_commands.Choice(name="DeepSeek", value="deepseek"),
        ]
    )
    async def ai_set(
        self,
        interaction: discord.Interaction,
        provider: str,
    ) -> None:
        """Set the AI provider."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Setting AI provider",
            guild_id=interaction.guild.id,
            provider=provider,
        )

        # Save to database
        async with get_session() as db:
            tenant = await get_tenant_for_guild(interaction.guild.id, db)
            if not tenant:
                await interaction.followup.send("Server not set up. Run `/setup` first.", ephemeral=True)
                return

            # Check if config exists for this provider
            result = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.tenant_id == tenant.id,
                    AIProviderConfig.provider == provider,
                )
            )
            config = result.scalar_one_or_none()

            if config:
                # Set as default
                config.is_default = True
            else:
                # Create new config (without API key)
                config = AIProviderConfig(
                    tenant_id=tenant.id,
                    provider=provider,
                    is_default=True,
                )
                db.add(config)

            # Unset default on other providers
            other_configs = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.tenant_id == tenant.id,
                    AIProviderConfig.provider != provider,
                )
            )
            for other in other_configs.scalars().all():
                other.is_default = False

        embed = discord.Embed(
            title="AI Provider Updated",
            description=f"Now using **{provider}** for AI analysis",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="API Key",
            value="Using system default key. Use `/config ai key` to set your own.",
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_group.command(name="key", description="Set your AI provider API key (DM only)")
    @app_commands.describe(
        provider="The AI provider",
        api_key="Your API key (will be encrypted)",
    )
    @app_commands.choices(
        provider=[
            app_commands.Choice(name="Claude (Anthropic)", value="claude"),
            app_commands.Choice(name="GPT-4 (OpenAI)", value="openai"),
            app_commands.Choice(name="Gemini (Google)", value="gemini"),
            app_commands.Choice(name="DeepSeek", value="deepseek"),
        ]
    )
    async def ai_key(
        self,
        interaction: discord.Interaction,
        provider: str,
        api_key: str,
    ) -> None:
        """Set API key for an AI provider."""
        # Warn if not in DM (for security)
        if interaction.guild:
            await interaction.response.send_message(
                "For security, please use this command in a DM with the bot, "
                "or the key will be visible in your server's audit log.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Setting AI API key",
            provider=provider,
            user_id=interaction.user.id,
        )

        # Note: In DM context, we need to know which guild/tenant this is for
        # For now, we'll handle this by requiring the user to specify or use their primary tenant
        # This is a simplified version - in production, you'd have a tenant selection flow

        embed = discord.Embed(
            title="API Key Setup",
            description=(
                f"To set your **{provider}** API key, please use the web dashboard "
                "or run this command in a server channel (the key will be hidden)."
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="API keys are encrypted before storage")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_group.command(name="status", description="Show current AI provider configuration")
    async def ai_status(self, interaction: discord.Interaction) -> None:
        """Show AI provider status."""
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
                select(AIProviderConfig).where(
                    AIProviderConfig.tenant_id == tenant.id,
                    AIProviderConfig.is_active == True,
                )
            )
            configs = result.scalars().all()

        embed = discord.Embed(
            title="AI Provider Status",
            description="Current AI configuration",
            color=discord.Color.blue(),
        )

        if configs:
            default_config = next((c for c in configs if c.is_default), configs[0])
            embed.add_field(name="Active Provider", value=default_config.provider.title(), inline=True)
            embed.add_field(
                name="API Key",
                value="Custom key configured" if default_config.api_key_encrypted else "System default",
                inline=True,
            )

            if len(configs) > 1:
                other_providers = [c.provider for c in configs if c != default_config]
                embed.add_field(
                    name="Other Configured",
                    value=", ".join(other_providers),
                    inline=False,
                )
        else:
            embed.add_field(name="Active Provider", value="Claude (default)", inline=True)
            embed.add_field(name="API Key", value="System default", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)


# Config command group (parent)
config_group = app_commands.Group(
    name="config",
    description="EldenOps configuration",
    default_permissions=discord.Permissions(administrator=True),
)


async def setup(bot: commands.Bot) -> None:
    """Load the Config cog."""
    cog = ConfigCog(bot)

    # Remove existing config command if present (handles restarts)
    existing = bot.tree.get_command("config")
    if existing:
        bot.tree.remove_command("config")

    # Add subgroups to main config group
    # Clear any existing subcommands first
    for cmd in list(config_group.walk_commands()):
        try:
            config_group.remove_command(cmd.name)
        except Exception:
            pass

    config_group.add_command(cog.channels_group)
    config_group.add_command(cog.github_group)
    config_group.add_command(cog.ai_group)

    # Add the main group to the bot
    bot.tree.add_command(config_group)

    await bot.add_cog(cog)
