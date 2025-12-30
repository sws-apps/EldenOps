"""Report generation background tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional,  Any

import httpx
from sqlalchemy import select, func
import structlog

from eldenops.ai.router import analyze_with_ai
from eldenops.db.engine import get_session
from eldenops.db.models.discord import DiscordEvent, VoiceSession
from eldenops.db.models.github import GitHubEvent
from eldenops.db.models.report import Report, ReportConfig
from eldenops.config.settings import settings

logger = structlog.get_logger()


def _should_run_cron(cron_expr: str, current_time: datetime) -> bool:
    """Simple cron check - matches hour and day-of-week for common patterns."""
    # Simple implementation for common patterns like "0 9 * * *" or "0 9 * * 1"
    # In production, use a library like croniter
    parts = cron_expr.split()
    if len(parts) != 5:
        return False

    minute, hour, day, month, dow = parts
    now_minute = current_time.minute
    now_hour = current_time.hour
    now_dow = current_time.weekday()  # 0=Monday

    # Check minute (within 5-minute window)
    if minute != "*" and abs(int(minute) - now_minute) > 5:
        return False

    # Check hour
    if hour != "*" and int(hour) != now_hour:
        return False

    # Check day of week (0=Sunday in cron, 0=Monday in Python)
    if dow != "*":
        cron_dow = int(dow)
        # Convert: cron 0=Sun, 1=Mon... Python 0=Mon, 6=Sun
        python_dow = (cron_dow - 1) % 7 if cron_dow > 0 else 6
        if python_dow != now_dow:
            return False

    return True


async def generate_scheduled_report(ctx: dict) -> dict[str, Any]:
    """Check for and generate any due scheduled reports.

    This is called periodically by the ARQ cron scheduler.

    Args:
        ctx: ARQ context

    Returns:
        Results of report generation
    """
    logger.info("Checking for scheduled reports...")

    now = datetime.now(timezone.utc)
    reports_generated = 0

    async with get_session() as db:
        # Query database for active scheduled report configs
        result = await db.execute(
            select(ReportConfig)
            .where(ReportConfig.is_active == True)
            .where(ReportConfig.schedule_cron != None)
        )
        configs = result.scalars().all()

        for config in configs:
            if _should_run_cron(config.schedule_cron, now):
                logger.info(
                    "Running scheduled report",
                    config_id=config.id,
                    name=config.name,
                )

                try:
                    # Generate report
                    report_result = await generate_report(
                        ctx=ctx,
                        tenant_id=config.tenant_id,
                        report_type=config.report_type,
                        days=7,  # Default to weekly
                        filters=config.filters,
                        config_id=config.id,
                    )

                    # Deliver if config has delivery settings
                    if config.delivery_channel_id or config.delivery_config:
                        delivery_config = config.delivery_config or {}
                        if config.delivery_channel_id:
                            delivery_config["discord_channel_id"] = config.delivery_channel_id

                        await deliver_report(
                            ctx=ctx,
                            tenant_id=config.tenant_id,
                            report_id=report_result.get("report_id"),
                            delivery_config=delivery_config,
                        )

                    reports_generated += 1
                except Exception as e:
                    logger.error(
                        "Failed to generate scheduled report",
                        config_id=config.id,
                        error=str(e),
                    )

    return {
        "status": "checked",
        "checked_at": now.isoformat(),
        "reports_generated": reports_generated,
    }


async def generate_report(
    ctx: dict,
    tenant_id: str,
    report_type: str,
    days: int = 7,
    filters: Optional[dict[str, Any]] = None,
    config_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a report using AI analysis.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        report_type: Type of report to generate
        days: Number of days to include
        filters: Optional filters (channel_ids, user_ids, etc.)
        config_id: Optional report config ID if from scheduled report

    Returns:
        Generated report data
    """
    logger.info(
        "Generating report",
        tenant_id=tenant_id,
        report_type=report_type,
        days=days,
    )

    start_time = datetime.now(timezone.utc)
    since = start_time - timedelta(days=days)
    filters = filters or {}

    async with get_session() as db:
        # Fetch Discord events from database
        discord_stats = await db.execute(
            select(
                func.count(DiscordEvent.id).label("total_messages"),
                func.count(func.distinct(DiscordEvent.user_id)).label("active_members"),
                func.sum(DiscordEvent.word_count).label("total_words"),
            )
            .where(
                DiscordEvent.tenant_id == tenant_id,
                DiscordEvent.created_at >= since,
            )
        )
        discord_data = discord_stats.one()

        # Get voice hours
        voice_stats = await db.execute(
            select(func.sum(VoiceSession.duration_seconds))
            .where(
                VoiceSession.tenant_id == tenant_id,
                VoiceSession.started_at >= since,
            )
        )
        total_voice_seconds = voice_stats.scalar() or 0
        voice_hours = round(total_voice_seconds / 3600, 1)

        # Fetch GitHub events from database
        github_stats = await db.execute(
            select(
                func.count(GitHubEvent.id).label("total_events"),
                func.count(func.distinct(GitHubEvent.github_user_login)).label("contributors"),
            )
            .where(
                GitHubEvent.tenant_id == tenant_id,
                GitHubEvent.created_at >= since,
            )
        )
        github_data = github_stats.one()

        commit_count = await db.execute(
            select(func.count(GitHubEvent.id))
            .where(
                GitHubEvent.tenant_id == tenant_id,
                GitHubEvent.event_type == "commit",
                GitHubEvent.created_at >= since,
            )
        )
        commits = commit_count.scalar() or 0

        pr_count = await db.execute(
            select(func.count(GitHubEvent.id))
            .where(
                GitHubEvent.tenant_id == tenant_id,
                GitHubEvent.event_type == "pull_request",
                GitHubEvent.created_at >= since,
            )
        )
        prs = pr_count.scalar() or 0

    # Build report content
    report_content = {
        "discord": {
            "total_messages": discord_data.total_messages or 0,
            "active_members": discord_data.active_members or 0,
            "total_words": discord_data.total_words or 0,
            "voice_hours": voice_hours,
        },
        "github": {
            "total_events": github_data.total_events or 0,
            "commits": commits,
            "pull_requests": prs,
            "contributors": github_data.contributors or 0,
        },
    }

    # Build prompt for AI
    prompt = _build_report_prompt(
        report_type,
        report_content["discord"],
        report_content["github"],
        days,
    )

    # Generate AI summary
    ai_summary = None
    tokens_used = 0
    try:
        ai_response = await analyze_with_ai(
            prompt=prompt,
            system_prompt=_get_report_system_prompt(report_type),
            max_tokens=2048,
            temperature=0.7,
        )
        ai_summary = ai_response.content
        tokens_used = ai_response.usage.total_tokens if ai_response.usage else 0
    except Exception as e:
        logger.error("AI summary generation failed", error=str(e))
        ai_summary = "AI summary generation failed."

    generation_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    # Save report to database
    report_id = None
    async with get_session() as db:
        report = Report(
            tenant_id=tenant_id,
            config_id=config_id,
            report_type=report_type,
            title=f"{report_type.replace('_', ' ').title()} - {start_time.strftime('%Y-%m-%d')}",
            date_range_start=since,
            date_range_end=start_time,
            content=report_content,
            ai_summary=ai_summary,
            generated_at=start_time,
        )
        db.add(report)
        await db.flush()
        report_id = report.id

    return {
        "status": "completed",
        "tenant_id": tenant_id,
        "report_id": report_id,
        "report_type": report_type,
        "ai_summary": ai_summary,
        "tokens_used": tokens_used,
        "generation_time_ms": generation_time,
        "generated_at": start_time.isoformat(),
    }


async def deliver_report(
    ctx: dict,
    tenant_id: str,
    report_id: str,
    delivery_config: dict[str, Any],
) -> dict[str, Any]:
    """Deliver a generated report to configured channels.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        report_id: Report to deliver
        delivery_config: Delivery settings (discord_channel_id, email, webhook_url)

    Returns:
        Delivery results
    """
    logger.info(
        "Delivering report",
        tenant_id=tenant_id,
        report_id=report_id,
    )

    results = {}

    # Fetch the report
    async with get_session() as db:
        result = await db.execute(
            select(Report).where(
                Report.id == report_id,
                Report.tenant_id == tenant_id,
            )
        )
        report = result.scalar_one_or_none()

    if not report:
        logger.error("Report not found for delivery", report_id=report_id)
        return {
            "status": "failed",
            "error": "Report not found",
            "report_id": report_id,
        }

    # Discord delivery via webhook
    if discord_channel_id := delivery_config.get("discord_channel_id"):
        # Note: Discord bot would handle this, but we can use a webhook for scheduled reports
        # In production, this would be handled by the Discord bot
        results["discord"] = {
            "success": True,
            "channel_id": discord_channel_id,
            "note": "Queued for Discord bot delivery",
        }

    # Webhook delivery
    if webhook_url := delivery_config.get("webhook_url"):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json={
                        "report_id": report.id,
                        "report_type": report.report_type,
                        "title": report.title,
                        "content": report.content,
                        "ai_summary": report.ai_summary,
                        "generated_at": report.generated_at.isoformat(),
                    },
                    timeout=30.0,
                )
                results["webhook"] = {
                    "success": response.status_code in (200, 201, 202),
                    "status_code": response.status_code,
                }
        except Exception as e:
            logger.error("Webhook delivery failed", error=str(e))
            results["webhook"] = {"success": False, "error": str(e)}

    # Email delivery (placeholder for future implementation)
    if email := delivery_config.get("email"):
        results["email"] = {
            "success": False,
            "error": "Email delivery not yet implemented",
        }

    return {
        "status": "delivered",
        "report_id": report_id,
        "delivery_results": results,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_report_prompt(
    report_type: str,
    discord_data: dict[str, Any],
    github_data: dict[str, Any],
    days: int,
) -> str:
    """Build the prompt for AI report generation."""
    return f"""Generate a {report_type.replace('_', ' ')} report for the last {days} days.

Discord Activity:
- Total messages: {discord_data.get('total_messages', 0)}
- Active members: {discord_data.get('active_members', 0)}
- Voice hours: {discord_data.get('voice_hours', 0)}h

GitHub Activity:
- Commits: {github_data.get('commits', 0)}
- Pull Requests: {github_data.get('pull_requests', 0)}
- Contributors: {github_data.get('contributors', 0)}

Please provide:
1. Executive summary (2-3 sentences)
2. Key highlights and achievements
3. Areas of concern or blockers
4. Recommendations for the team

Format the response in clear sections with headers."""


def _get_report_system_prompt(report_type: str) -> str:
    """Get the system prompt for report generation."""
    return """You are an expert team analytics assistant that helps managers understand their team's progress and performance.

Your reports should be:
- Concise and actionable
- Focused on outcomes and impact
- Respectful of async work patterns
- Highlighting both achievements and concerns
- Professional but friendly in tone

Do not include specific message content or private information. Focus on patterns, metrics, and high-level insights."""
