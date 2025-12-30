"""Global state for Discord bot access from API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from eldenops.integrations.discord.bot import EldenBot

# Global bot instance reference
_bot_instance: Optional["EldenBot"] = None


def set_bot(bot: "EldenBot") -> None:
    """Set the global bot instance."""
    global _bot_instance
    _bot_instance = bot


def get_bot() -> Optional["EldenBot"]:
    """Get the global bot instance."""
    return _bot_instance
