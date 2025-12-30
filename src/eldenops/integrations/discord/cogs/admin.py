"""Admin commands for server setup and management."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
import structlog

from eldenops.config.constants import TenantRole
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant, TenantMember, AIProviderConfig
from eldenops.db.models.discord import MonitoredChannel
from eldenops.db.models.github import GitHubConnection
from eldenops.db.models.report import ReportConfig
from eldenops.db.models.user import User
from eldenops.integrations.discord.utils.permissions import is_admin_or_owner

logger = structlog.get_logger()


class AdminCog(commands.Cog, name="Admin"):
    """Administrative commands for EldenOps setup."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="Set up EldenOps for this server")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction) -> None:
        """Initial setup wizard for new servers."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        logger.info(
            "Starting setup",
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        # Create or update tenant in database
        async with get_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.discord_guild_id == interaction.guild.id)
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                # Create new tenant
                icon_url = str(interaction.guild.icon.url) if interaction.guild.icon else None
                tenant = Tenant(
                    discord_guild_id=interaction.guild.id,
                    guild_name=interaction.guild.name,
                    guild_icon_url=icon_url,
                    owner_discord_id=interaction.guild.owner_id,
                )
                db.add(tenant)
                await db.flush()

                # Create or get the user running setup
                user_result = await db.execute(
                    select(User).where(User.discord_id == interaction.user.id)
                )
                user = user_result.scalar_one_or_none()

                if not user:
                    user = User(
                        discord_id=interaction.user.id,
                        discord_username=interaction.user.name,
                    )
                    db.add(user)
                    await db.flush()

                # Add user as tenant admin/owner
                role = TenantRole.OWNER if interaction.user.id == interaction.guild.owner_id else TenantRole.ADMIN
                membership = TenantMember(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role=role,
                )
                db.add(membership)
            else:
                # Update existing tenant
                tenant.guild_name = interaction.guild.name
                tenant.is_active = True

        # Create embed for setup status
        embed = discord.Embed(
            title="EldenOps Setup",
            description="Setting up EldenOps for your server...",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Server Registered",
            value=f"Server: {interaction.guild.name}",
            inline=False,
        )

        embed.add_field(
            name="Next Steps",
            value=(
                "1. Use `/config channels add` to select channels to monitor\n"
                "2. Use `/config github connect` to link GitHub repositories\n"
                "3. Use `/config ai set` to configure your AI provider\n"
                "4. Use `/report generate` to create your first report"
            ),
            inline=False,
        )

        embed.set_footer(text="Only server admins and owners can configure EldenOps")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Show EldenOps configuration status")
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction) -> None:
        """Show current configuration status."""
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch actual config from database
        async with get_session() as db:
            # Get tenant
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.discord_guild_id == interaction.guild.id)
            )
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                await interaction.followup.send(
                    "Server not set up yet. Run `/setup` first.",
                    ephemeral=True,
                )
                return

            # Get monitored channels
            channels_result = await db.execute(
                select(MonitoredChannel).where(
                    MonitoredChannel.tenant_id == tenant.id,
                    MonitoredChannel.is_active == True,
                )
            )
            channels = channels_result.scalars().all()

            # Get GitHub connections
            github_result = await db.execute(
                select(GitHubConnection).where(
                    GitHubConnection.tenant_id == tenant.id,
                    GitHubConnection.is_active == True,
                )
            )
            github_connections = github_result.scalars().all()

            # Get AI provider config
            ai_result = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.tenant_id == tenant.id,
                    AIProviderConfig.is_active == True,
                )
            )
            ai_configs = ai_result.scalars().all()

            # Get scheduled reports
            reports_result = await db.execute(
                select(ReportConfig).where(
                    ReportConfig.tenant_id == tenant.id,
                    ReportConfig.is_active == True,
                    ReportConfig.schedule_cron != None,
                )
            )
            scheduled_reports = reports_result.scalars().all()

        embed = discord.Embed(
            title="EldenOps Status",
            description=f"Configuration for **{interaction.guild.name}**",
            color=discord.Color.green(),
        )

        # Monitored channels
        if channels:
            channel_list = "\n".join([f"• <#{ch.channel_id}> ({ch.channel_type})" for ch in channels[:5]])
            if len(channels) > 5:
                channel_list += f"\n... and {len(channels) - 5} more"
            embed.add_field(name="Monitored Channels", value=channel_list, inline=False)
        else:
            embed.add_field(
                name="Monitored Channels",
                value="No channels configured yet\nUse `/config channels add`",
                inline=False,
            )

        # GitHub connections
        if github_connections:
            repo_list = "\n".join([f"• `{conn.repo_full_name}`" for conn in github_connections[:5]])
            if len(github_connections) > 5:
                repo_list += f"\n... and {len(github_connections) - 5} more"
            embed.add_field(name="GitHub Connections", value=repo_list, inline=False)
        else:
            embed.add_field(
                name="GitHub Connections",
                value="No repositories connected\nUse `/config github connect`",
                inline=False,
            )

        # AI provider
        if ai_configs:
            default_config = next((c for c in ai_configs if c.is_default), ai_configs[0])
            embed.add_field(
                name="AI Provider",
                value=f"Using **{default_config.provider}** (custom key)",
                inline=False,
            )
        else:
            embed.add_field(
                name="AI Provider",
                value="Using default (Claude)\nUse `/config ai set` to change",
                inline=False,
            )

        # Scheduled reports
        if scheduled_reports:
            report_list = "\n".join([f"• {r.name} ({r.report_type})" for r in scheduled_reports[:3]])
            embed.add_field(name="Scheduled Reports", value=report_list, inline=False)
        else:
            embed.add_field(
                name="Scheduled Reports",
                value="None configured\nUse `/report schedule` to set up",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Show EldenOps help and available commands")
    async def help(self, interaction: discord.Interaction) -> None:
        """Show help information."""
        embed = discord.Embed(
            title="EldenOps Help",
            description="AI-powered team analytics for Discord + GitHub",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Setup Commands (Admin only)",
            value=(
                "`/setup` - Initial server setup\n"
                "`/status` - Show configuration status\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Configuration Commands (Admin only)",
            value=(
                "`/config channels add` - Add channel to monitor\n"
                "`/config channels remove` - Stop monitoring a channel\n"
                "`/config channels list` - List monitored channels\n"
                "`/config github connect` - Connect a GitHub repo\n"
                "`/config github list` - List connected repos\n"
                "`/config ai set` - Set AI provider\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Report Commands (Admin only)",
            value=(
                "`/report generate` - Generate an on-demand report\n"
                "`/report schedule` - Set up scheduled reports\n"
            ),
            inline=False,
        )

        embed.set_footer(text="EldenOps - Building high-performing async teams")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Admin cog."""
    await bot.add_cog(AdminCog(bot))
