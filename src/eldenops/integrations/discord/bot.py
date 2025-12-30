"""Main Discord bot class."""

from __future__ import annotations

import discord
from discord.ext import commands
from sqlalchemy import select, update
import structlog

from eldenops.config.settings import settings
from eldenops.config.constants import TenantRole
from eldenops.db.engine import get_session
from eldenops.db.models.tenant import Tenant, TenantMember
from eldenops.db.models.user import User

logger = structlog.get_logger()


class EldenBot(commands.Bot):
    """EldenOps Discord bot."""

    def __init__(self) -> None:
        """Initialize the bot with required intents."""
        intents = discord.Intents.default()
        intents.message_content = True  # For message tracking
        intents.guilds = True
        intents.members = True  # For member info
        intents.voice_states = True  # For voice tracking

        super().__init__(
            command_prefix="!",  # Fallback, we use slash commands
            intents=intents,
            help_command=None,
        )

        self._ready = False

    async def setup_hook(self) -> None:
        """Called when the bot is starting up."""
        logger.info("Setting up EldenOps bot...")

        # Load cogs
        await self._load_cogs()

        # Sync slash commands
        logger.info("Syncing slash commands...")
        await self.tree.sync()

        logger.info("Bot setup complete")

    async def _load_cogs(self) -> None:
        """Load all cogs and event handlers."""
        # Command cogs
        cog_modules = [
            "eldenops.integrations.discord.cogs.admin",
            "eldenops.integrations.discord.cogs.attendance",
            "eldenops.integrations.discord.cogs.sync",
            # config and reports moved to dashboard UI
        ]

        # Event handlers
        event_modules = [
            "eldenops.integrations.discord.events.messages",
            "eldenops.integrations.discord.events.voice",
            "eldenops.integrations.discord.events.attendance",
        ]

        for module in cog_modules + event_modules:
            try:
                await self.load_extension(module)
                logger.info("Loaded extension", module=module)
            except Exception as e:
                logger.error("Failed to load extension", module=module, error=str(e))

    async def on_ready(self) -> None:
        """Called when bot is connected and ready."""
        if self._ready:
            return

        self._ready = True
        logger.info(
            "EldenOps bot is ready",
            user=str(self.user),
            guilds=len(self.guilds),
        )

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="team progress",
            )
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when bot joins a new server."""
        logger.info(
            "Joined new guild",
            guild_id=guild.id,
            guild_name=guild.name,
            member_count=guild.member_count,
        )

        async with get_session() as db:
            # Check if tenant already exists (bot was re-added)
            result = await db.execute(
                select(Tenant).where(Tenant.discord_guild_id == guild.id)
            )
            tenant = result.scalar_one_or_none()

            if tenant:
                # Reactivate existing tenant
                tenant.is_active = True
                tenant.guild_name = guild.name
                tenant.guild_icon_url = str(guild.icon.url) if guild.icon else None
                logger.info("Reactivated existing tenant", tenant_id=tenant.id)
            else:
                # Create new tenant record
                icon_url = str(guild.icon.url) if guild.icon else None
                tenant = Tenant(
                    discord_guild_id=guild.id,
                    guild_name=guild.name,
                    guild_icon_url=icon_url,
                    owner_discord_id=guild.owner_id,
                )
                db.add(tenant)
                await db.flush()

                # Create or get the owner user and add as tenant owner
                owner_result = await db.execute(
                    select(User).where(User.discord_id == guild.owner_id)
                )
                owner_user = owner_result.scalar_one_or_none()

                if not owner_user:
                    owner = guild.owner
                    owner_user = User(
                        discord_id=guild.owner_id,
                        discord_username=owner.name if owner else None,
                    )
                    db.add(owner_user)
                    await db.flush()

                # Add owner as tenant member
                membership = TenantMember(
                    tenant_id=tenant.id,
                    user_id=owner_user.id,
                    role=TenantRole.OWNER,
                )
                db.add(membership)

                logger.info("Created new tenant", tenant_id=tenant.id)

        # Send welcome message to system channel
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            embed = discord.Embed(
                title="EldenOps is ready!",
                description=(
                    "Thanks for adding EldenOps to your server.\n\n"
                    "**Get started:**\n"
                    "• `/setup` - Run initial setup\n"
                    "• `/help` - View all commands\n"
                    "• `/config channels add` - Start monitoring channels"
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text="Only server admins can configure EldenOps")
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when bot is removed from a server."""
        logger.info(
            "Removed from guild",
            guild_id=guild.id,
            guild_name=guild.name,
        )

        # Mark tenant as inactive (don't delete data)
        async with get_session() as db:
            await db.execute(
                update(Tenant)
                .where(Tenant.discord_guild_id == guild.id)
                .values(is_active=False)
            )
            logger.info("Marked tenant as inactive", guild_id=guild.id)

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Global error handler for commands."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        elif isinstance(error, commands.CommandNotFound):
            pass  # Ignore unknown commands
        else:
            logger.error(
                "Command error",
                command=ctx.command,
                error=str(error),
                guild_id=ctx.guild.id if ctx.guild else None,
            )
            await ctx.send(
                "An error occurred while processing your command.",
                ephemeral=True,
            )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Global error handler for slash commands."""
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        else:
            logger.error(
                "Slash command error",
                command=interaction.command.name if interaction.command else "unknown",
                error=str(error),
                guild_id=interaction.guild_id,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your command.",
                    ephemeral=True,
                )
