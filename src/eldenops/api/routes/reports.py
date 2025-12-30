"""Report endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional,  Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
import structlog

from eldenops.ai.router import analyze_with_ai
from eldenops.api.deps import CurrentUser, DBSession, TenantID
from eldenops.db.models.discord import DiscordEvent, VoiceSession
from eldenops.db.models.github import GitHubEvent
from eldenops.db.models.report import Report, ReportConfig
from eldenops.db.models.attendance import AttendanceLog

logger = structlog.get_logger()
router = APIRouter()


class ReportConfigCreate(BaseModel):
    """Request to create a report configuration."""

    name: str
    report_type: str = "weekly_digest"
    schedule_cron: Optional[str] = None
    filters: dict[str, Any] = {}
    delivery_config: dict[str, Any] = {}
    ai_summary_enabled: bool = True


class ReportConfigResponse(BaseModel):
    """Report configuration response."""

    id: str
    name: str
    report_type: str
    schedule_cron: Optional[str]
    filters: dict[str, Any]
    delivery_config: dict[str, Any]
    ai_summary_enabled: bool
    is_active: bool
    created_at: datetime


class ReportResponse(BaseModel):
    """Generated report response."""

    id: str
    config_id: Optional[str]
    report_type: str
    title: str
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    content: dict[str, Any]
    ai_summary: Optional[str]
    generated_at: datetime


class GenerateReportRequest(BaseModel):
    """Request to generate an on-demand report."""

    report_type: str = "weekly_digest"
    days: int = 7
    filters: dict[str, Any] = {}


# Report configurations
@router.get("/configs")
async def list_report_configs(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[ReportConfigResponse]:
    """List all report configurations for a tenant."""
    logger.info("Listing report configs", tenant_id=tenant_id)

    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.tenant_id == tenant_id,
            ReportConfig.is_active == True,
        )
    )
    configs = result.scalars().all()

    return [
        ReportConfigResponse(
            id=cfg.id,
            name=cfg.name,
            report_type=cfg.report_type,
            schedule_cron=cfg.schedule_cron,
            filters=cfg.filters or {},
            delivery_config=cfg.delivery_config or {},
            ai_summary_enabled=cfg.ai_summary_enabled,
            is_active=cfg.is_active,
            created_at=cfg.created_at,
        )
        for cfg in configs
    ]


@router.post("/configs")
async def create_report_config(
    request: ReportConfigCreate,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ReportConfigResponse:
    """Create a new report configuration."""
    logger.info(
        "Creating report config",
        tenant_id=tenant_id,
        name=request.name,
        report_type=request.report_type,
    )

    config = ReportConfig(
        tenant_id=tenant_id,
        name=request.name,
        report_type=request.report_type,
        schedule_cron=request.schedule_cron,
        filters=request.filters,
        delivery_config=request.delivery_config,
        ai_summary_enabled=request.ai_summary_enabled,
    )
    db.add(config)
    await db.flush()

    return ReportConfigResponse(
        id=config.id,
        name=config.name,
        report_type=config.report_type,
        schedule_cron=config.schedule_cron,
        filters=config.filters or {},
        delivery_config=config.delivery_config or {},
        ai_summary_enabled=config.ai_summary_enabled,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.get("/configs/{config_id}")
async def get_report_config(
    config_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ReportConfigResponse:
    """Get a specific report configuration."""
    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.id == config_id,
            ReportConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report config not found",
        )

    return ReportConfigResponse(
        id=config.id,
        name=config.name,
        report_type=config.report_type,
        schedule_cron=config.schedule_cron,
        filters=config.filters or {},
        delivery_config=config.delivery_config or {},
        ai_summary_enabled=config.ai_summary_enabled,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.patch("/configs/{config_id}")
async def update_report_config(
    config_id: str,
    request: ReportConfigCreate,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ReportConfigResponse:
    """Update a report configuration."""
    logger.info("Updating report config", config_id=config_id)

    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.id == config_id,
            ReportConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report config not found",
        )

    config.name = request.name
    config.report_type = request.report_type
    config.schedule_cron = request.schedule_cron
    config.filters = request.filters
    config.delivery_config = request.delivery_config
    config.ai_summary_enabled = request.ai_summary_enabled

    return ReportConfigResponse(
        id=config.id,
        name=config.name,
        report_type=config.report_type,
        schedule_cron=config.schedule_cron,
        filters=config.filters or {},
        delivery_config=config.delivery_config or {},
        ai_summary_enabled=config.ai_summary_enabled,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.delete("/configs/{config_id}")
async def delete_report_config(
    config_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """Delete a report configuration."""
    logger.info("Deleting report config", config_id=config_id)

    result = await db.execute(
        select(ReportConfig).where(
            ReportConfig.id == config_id,
            ReportConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report config not found",
        )

    config.is_active = False
    return {"message": "Report config deleted"}


# Generated reports
@router.get("")
async def list_reports(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ReportResponse]:
    """List generated reports for a tenant."""
    logger.info(
        "Listing reports",
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )

    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == tenant_id)
        .order_by(Report.generated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reports = result.scalars().all()

    return [
        ReportResponse(
            id=r.id,
            config_id=r.config_id,
            report_type=r.report_type,
            title=r.title,
            date_range_start=r.date_range_start,
            date_range_end=r.date_range_end,
            content=r.content or {},
            ai_summary=r.ai_summary,
            generated_at=r.generated_at,
        )
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ReportResponse:
    """Get a specific generated report."""
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.tenant_id == tenant_id,
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return ReportResponse(
        id=report.id,
        config_id=report.config_id,
        report_type=report.report_type,
        title=report.title,
        date_range_start=report.date_range_start,
        date_range_end=report.date_range_end,
        content=report.content or {},
        ai_summary=report.ai_summary,
        generated_at=report.generated_at,
    )


@router.post("/generate")
async def generate_report(
    request: GenerateReportRequest,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ReportResponse:
    """Generate an on-demand report.

    Report types:
    - operations: Attendance-focused for Operations Manager / Team Lead
    - engineering: Development-focused for CTO / Engineering Manager
    - executive: High-level summary for CEO / Executive Leadership
    - daily: Daily summary (default)
    - weekly: Weekly comprehensive report
    """
    logger.info(
        "Generating on-demand report",
        tenant_id=tenant_id,
        report_type=request.report_type,
        days=request.days,
    )

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=request.days)

    # ===== ATTENDANCE DATA =====
    # Get attendance event counts
    attendance_stats = await db.execute(
        select(
            AttendanceLog.event_type,
            func.count(AttendanceLog.id).label("count"),
        )
        .where(
            AttendanceLog.tenant_id == tenant_id,
            AttendanceLog.event_time >= since,
        )
        .group_by(AttendanceLog.event_type)
    )
    attendance_counts = {row.event_type: row.count for row in attendance_stats.fetchall()}

    # Get unique users who had attendance events
    unique_attendance_users = await db.execute(
        select(func.count(func.distinct(AttendanceLog.user_id)))
        .where(
            AttendanceLog.tenant_id == tenant_id,
            AttendanceLog.event_time >= since,
        )
    )
    attendance_user_count = unique_attendance_users.scalar() or 0

    # Calculate average work hours (time between check-in and check-out)
    # This is a simplified calculation
    checkin_count = attendance_counts.get("checkin", 0)
    checkout_count = attendance_counts.get("checkout", 0)
    break_start_count = attendance_counts.get("break_start", 0)
    break_end_count = attendance_counts.get("break_end", 0)

    attendance_data = {
        "total_checkins": checkin_count,
        "total_checkouts": checkout_count,
        "total_breaks": break_start_count,
        "unique_team_members": attendance_user_count,
        "attendance_rate": f"{min(checkin_count / max(request.days * attendance_user_count, 1) * 100, 100):.0f}%" if attendance_user_count > 0 else "N/A",
    }

    # ===== DISCORD DATA =====
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

    discord_content = {
        "total_messages": discord_data.total_messages or 0,
        "active_members": discord_data.active_members or 0,
        "total_words": discord_data.total_words or 0,
        "voice_hours": voice_hours,
    }

    # ===== GITHUB DATA =====
    github_stats = await db.execute(
        select(
            func.count(GitHubEvent.id).label("total_events"),
            func.count(func.distinct(GitHubEvent.github_user_login)).label("contributors"),
            func.sum(GitHubEvent.additions).label("lines_added"),
            func.sum(GitHubEvent.deletions).label("lines_deleted"),
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

    issue_count = await db.execute(
        select(func.count(GitHubEvent.id))
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.event_type == "issue",
            GitHubEvent.created_at >= since,
        )
    )
    issues = issue_count.scalar() or 0

    github_content = {
        "total_events": github_data.total_events or 0,
        "commits": commits,
        "pull_requests": prs,
        "issues": issues,
        "contributors": github_data.contributors or 0,
        "lines_added": github_data.lines_added or 0,
        "lines_deleted": github_data.lines_deleted or 0,
    }

    # ===== BUILD REPORT CONTENT BASED ON TYPE =====
    report_type = request.report_type.lower()

    if report_type == "operations":
        # Operations Manager / Team Lead - Focus on attendance
        report_content = {
            "attendance": attendance_data,
            "team_activity": {
                "discord_messages": discord_content["total_messages"],
                "voice_hours": discord_content["voice_hours"],
                "active_members": discord_content["active_members"],
            },
        }
        title = f"Operations Report - {now.strftime('%Y-%m-%d')}"
        ai_focus = "attendance patterns, team availability, and operational efficiency"

    elif report_type == "engineering":
        # CTO / Engineering Manager - Focus on development
        report_content = {
            "development": github_content,
            "code_velocity": {
                "commits_per_day": round(commits / max(request.days, 1), 1),
                "prs_per_day": round(prs / max(request.days, 1), 1),
                "net_lines_changed": (github_data.lines_added or 0) - (github_data.lines_deleted or 0),
            },
            "team_size": {
                "contributors": github_content["contributors"],
                "active_discord_members": discord_content["active_members"],
            },
        }
        title = f"Engineering Report - {now.strftime('%Y-%m-%d')}"
        ai_focus = "development velocity, code output, contributor productivity, and technical progress"

    elif report_type == "executive":
        # CEO / Executive Leadership - High-level summary
        report_content = {
            "summary": {
                "team_members_active": max(attendance_user_count, discord_content["active_members"], github_content["contributors"]),
                "attendance_rate": attendance_data["attendance_rate"],
                "total_commits": commits,
                "total_prs": prs,
            },
            "productivity": {
                "code_changes": f"+{github_data.lines_added or 0}/-{github_data.lines_deleted or 0}",
                "discord_engagement": discord_content["total_messages"],
                "voice_collaboration_hours": voice_hours,
            },
            "health_indicators": {
                "team_checkins": checkin_count,
                "breaks_taken": break_start_count,
                "contributors": github_content["contributors"],
            },
        }
        title = f"Executive Summary - {now.strftime('%Y-%m-%d')}"
        ai_focus = "overall team health, productivity trends, and strategic insights for leadership"

    else:
        # Default: daily/weekly/progress/blockers - comprehensive report
        report_content = {
            "attendance": attendance_data,
            "discord": discord_content,
            "github": github_content,
        }
        title = f"{report_type.replace('_', ' ').title()} - {now.strftime('%Y-%m-%d')}"
        ai_focus = "overall team activity and insights"

    # ===== AI SUMMARY =====
    ai_summary = None
    has_data = (
        attendance_user_count > 0 or
        discord_data.total_messages or
        github_data.total_events
    )

    if has_data:
        try:
            summary_prompt = f"""
            Generate a {report_type.replace('_', ' ')} report for the last {request.days} days.
            Focus on: {ai_focus}

            Attendance Data:
            - Check-ins: {checkin_count}
            - Check-outs: {checkout_count}
            - Breaks taken: {break_start_count}
            - Team members tracked: {attendance_user_count}

            Discord Activity:
            - Messages: {discord_data.total_messages or 0}
            - Active members: {discord_data.active_members or 0}
            - Voice hours: {voice_hours}h

            GitHub Activity:
            - Commits: {commits}
            - Pull Requests: {prs}
            - Issues: {issues}
            - Contributors: {github_data.contributors or 0}
            - Lines added: {github_data.lines_added or 0}
            - Lines deleted: {github_data.lines_deleted or 0}

            Provide a concise report with:
            1. Executive summary (2-3 sentences highlighting key metrics)
            2. Key highlights (bullet points)
            3. Actionable recommendations
            """
            ai_response = await analyze_with_ai(
                prompt=summary_prompt,
                system_prompt=f"You are an expert team analytics assistant generating reports for stakeholders. Provide concise, actionable insights focused on {ai_focus}.",
                max_tokens=1024,
                temperature=0.7,
            )
            ai_summary = ai_response.content
        except Exception as e:
            logger.error("AI summary failed", error=str(e))
            ai_summary = "AI summary generation is currently unavailable."
    else:
        ai_summary = f"No activity data found for the last {request.days} days."

    # ===== SAVE REPORT =====
    report = Report(
        tenant_id=tenant_id,
        report_type=request.report_type,
        title=title,
        date_range_start=since,
        date_range_end=now,
        content=report_content,
        ai_summary=ai_summary,
        generated_at=now,
    )
    db.add(report)
    await db.flush()

    return ReportResponse(
        id=report.id,
        config_id=report.config_id,
        report_type=report.report_type,
        title=report.title,
        date_range_start=report.date_range_start,
        date_range_end=report.date_range_end,
        content=report.content or {},
        ai_summary=report.ai_summary,
        generated_at=report.generated_at,
    )


@router.post("/{report_id}/deliver")
async def redeliver_report(
    report_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    channel: str = Query(default="discord"),
) -> dict:
    """Re-deliver an existing report."""
    logger.info(
        "Re-delivering report",
        report_id=report_id,
        channel=channel,
    )

    # Fetch report
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.tenant_id == tenant_id,
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Note: Actual delivery would be handled by background tasks
    # For now, just mark as delivered
    return {"message": f"Report queued for delivery to {channel}", "report_id": report_id}
