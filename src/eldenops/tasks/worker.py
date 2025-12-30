"""ARQ worker configuration."""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings
import structlog

from eldenops.config.settings import settings
from eldenops.tasks.discord_tasks import process_discord_event
from eldenops.tasks.github_tasks import process_github_event, sync_github_repo
from eldenops.tasks.report_tasks import generate_scheduled_report

logger = structlog.get_logger()


async def startup(ctx: dict) -> None:
    """Worker startup - initialize resources."""
    logger.info("ARQ worker starting up...")
    # Initialize database connection, AI providers, etc.


async def shutdown(ctx: dict) -> None:
    """Worker shutdown - cleanup resources."""
    logger.info("ARQ worker shutting down...")


class WorkerSettings:
    """ARQ worker settings."""

    # Redis connection
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))

    # Available task functions
    functions = [
        process_discord_event,
        process_github_event,
        sync_github_repo,
        generate_scheduled_report,
    ]

    # Scheduled jobs (cron)
    cron_jobs = [
        # Check for scheduled reports every minute
        cron(
            generate_scheduled_report,
            minute={0, 15, 30, 45},  # Every 15 minutes
            run_at_startup=False,
        ),
    ]

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Worker configuration
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # Keep results for 1 hour
    retry_jobs = True
    max_tries = 3
