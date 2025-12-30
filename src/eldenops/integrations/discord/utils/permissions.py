"""Permission checking utilities for Discord."""

from __future__ import annotations

import discord
from discord.ext import commands


def is_admin_or_owner():
    """Check if user is admin or server owner."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False

        # Check if server owner
        if ctx.author.id == ctx.guild.owner_id:
            return True

        # Check if has administrator permission
        if isinstance(ctx.author, discord.Member):
            return ctx.author.guild_permissions.administrator

        return False

    return commands.check(predicate)


def has_admin_role(member: discord.Member) -> bool:
    """Check if a member has administrator permissions."""
    return member.guild_permissions.administrator


def is_guild_owner(member: discord.Member) -> bool:
    """Check if a member is the guild owner."""
    return member.id == member.guild.owner_id


async def check_bot_permissions(
    channel: discord.TextChannel | discord.VoiceChannel,
) -> dict[str, bool]:
    """Check what permissions the bot has in a channel.

    Returns a dict of permission name -> has_permission.
    """
    if not channel.guild.me:
        return {}

    perms = channel.permissions_for(channel.guild.me)

    return {
        "send_messages": perms.send_messages,
        "embed_links": perms.embed_links,
        "read_messages": perms.read_messages,
        "read_message_history": perms.read_message_history,
        "add_reactions": perms.add_reactions,
        "connect": perms.connect if isinstance(channel, discord.VoiceChannel) else True,
    }
