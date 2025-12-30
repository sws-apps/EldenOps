"""EldenOps entry point."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import NoReturn

import structlog

from eldenops.config.settings import settings

logger = structlog.get_logger()


async def start_services() -> None:
    """Start all EldenOps services."""
    from eldenops.api.app import create_app
    from eldenops.integrations.discord.bot import EldenBot
    from eldenops.integrations.discord.state import set_bot

    # Initialize the Discord bot
    bot = EldenBot()
    set_bot(bot)  # Make bot accessible to API endpoints

    # Create FastAPI app
    app = create_app()

    # Start uvicorn server
    import uvicorn

    config = uvicorn.Config(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    # Run both bot and API server concurrently
    async def run_bot() -> None:
        try:
            logger.info("Starting Discord bot connection...")
            await bot.start(settings.discord_bot_token.get_secret_value())
        except Exception as e:
            logger.error("Discord bot error", error=str(e), exc_info=True)
            raise

    async def run_server() -> None:
        try:
            await server.serve()
        except Exception as e:
            logger.error("API server error", error=str(e))
            raise

    # Handle shutdown gracefully
    shutdown_event = asyncio.Event()

    def signal_handler(sig: signal.Signals) -> None:
        logger.info("Received shutdown signal", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    try:
        logger.info(
            "Starting EldenOps",
            version="0.1.0",
            environment=settings.app_env,
            api_port=settings.app_port,
        )

        # Run bot and server concurrently
        await asyncio.gather(
            run_bot(),
            run_server(),
            return_exceptions=True,
        )
    except Exception as e:
        logger.error("Service error", error=str(e))
    finally:
        # Cleanup
        if not bot.is_closed():
            await bot.close()
        logger.info("EldenOps shutdown complete")


def main() -> NoReturn:
    """Main entry point."""
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
