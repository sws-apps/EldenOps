"""Analytics data endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List,  Optional,  Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, case, cast, Date
from sqlalchemy.orm import selectinload
import structlog

from eldenops.api.deps import CurrentUser, DBSession, TenantID
from eldenops.db.models.discord import DiscordEvent, VoiceSession
from eldenops.db.models.github import GitHubEvent
from eldenops.db.models.user import User

logger = structlog.get_logger()
router = APIRouter()


class OverviewMetrics(BaseModel):
    """Overview metrics for dashboard."""

    discord_messages: int
    discord_active_users: int
    discord_voice_hours: float
    github_commits: int
    github_prs_merged: int
    github_issues_closed: int
    period_days: int


class ActivityDataPoint(BaseModel):
    """Single data point for activity charts."""

    date: str
    discord_messages: int
    github_commits: int
    github_prs: int


class UserActivitySummary(BaseModel):
    """Activity summary for a single user."""

    user_id: str
    discord_username: Optional[str]
    github_username: Optional[str]
    discord_messages: int
    discord_voice_minutes: int
    github_commits: int
    github_prs: int
    github_reviews: int


class CorrelationInsight(BaseModel):
    """Discord-GitHub correlation insight."""

    topic: str
    discord_mentions: int
    github_activity: int
    correlation_strength: str  # high, medium, low
    summary: str


@router.get("/overview")
async def get_overview(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> OverviewMetrics:
    """Get overview metrics for the dashboard."""
    logger.info(
        "Getting overview metrics",
        tenant_id=tenant_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Discord metrics
    discord_stats = await db.execute(
        select(
            func.count(DiscordEvent.id).label("total_messages"),
            func.count(func.distinct(DiscordEvent.user_id)).label("active_users"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
        )
    )
    discord_data = discord_stats.one()

    # Voice hours
    voice_stats = await db.execute(
        select(func.sum(VoiceSession.duration_seconds))
        .where(
            VoiceSession.tenant_id == tenant_id,
            VoiceSession.started_at >= since,
        )
    )
    total_voice_seconds = voice_stats.scalar() or 0
    voice_hours = round(total_voice_seconds / 3600, 1)

    # GitHub metrics
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

    return OverviewMetrics(
        discord_messages=discord_data.total_messages or 0,
        discord_active_users=discord_data.active_users or 0,
        discord_voice_hours=voice_hours,
        github_commits=commits,
        github_prs_merged=prs,
        github_issues_closed=issues,
        period_days=days,
    )


@router.get("/activity")
async def get_activity_timeline(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
    granularity: str = Query(default="daily", pattern="^(hourly|daily|weekly)$"),
) -> list[ActivityDataPoint]:
    """Get activity timeline data for charts."""
    logger.info(
        "Getting activity timeline",
        tenant_id=tenant_id,
        days=days,
        granularity=granularity,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    data_points = []

    # Get daily aggregates for Discord
    discord_daily = await db.execute(
        select(
            cast(DiscordEvent.created_at, Date).label("date"),
            func.count(DiscordEvent.id).label("count"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
        )
        .group_by(cast(DiscordEvent.created_at, Date))
        .order_by(cast(DiscordEvent.created_at, Date))
    )
    discord_by_date = {str(row.date): row.count for row in discord_daily}

    # Get daily aggregates for GitHub commits
    github_commits_daily = await db.execute(
        select(
            cast(GitHubEvent.created_at, Date).label("date"),
            func.count(GitHubEvent.id).label("count"),
        )
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.event_type == "commit",
            GitHubEvent.created_at >= since,
        )
        .group_by(cast(GitHubEvent.created_at, Date))
        .order_by(cast(GitHubEvent.created_at, Date))
    )
    commits_by_date = {str(row.date): row.count for row in github_commits_daily}

    # Get daily aggregates for GitHub PRs
    github_prs_daily = await db.execute(
        select(
            cast(GitHubEvent.created_at, Date).label("date"),
            func.count(GitHubEvent.id).label("count"),
        )
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.event_type == "pull_request",
            GitHubEvent.created_at >= since,
        )
        .group_by(cast(GitHubEvent.created_at, Date))
        .order_by(cast(GitHubEvent.created_at, Date))
    )
    prs_by_date = {str(row.date): row.count for row in github_prs_daily}

    # Build timeline
    current_date = since.date()
    end_date = datetime.now(timezone.utc).date()
    while current_date <= end_date:
        date_str = str(current_date)
        data_points.append(ActivityDataPoint(
            date=date_str,
            discord_messages=discord_by_date.get(date_str, 0),
            github_commits=commits_by_date.get(date_str, 0),
            github_prs=prs_by_date.get(date_str, 0),
        ))
        current_date += timedelta(days=1)

    return data_points


@router.get("/users")
async def get_user_activity(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> list[UserActivitySummary]:
    """Get activity summary per user."""
    logger.info(
        "Getting user activity",
        tenant_id=tenant_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get Discord activity by user
    discord_by_user = await db.execute(
        select(
            DiscordEvent.user_id,
            func.count(DiscordEvent.id).label("message_count"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
            DiscordEvent.user_id != None,
        )
        .group_by(DiscordEvent.user_id)
    )
    discord_data = {row.user_id: row.message_count for row in discord_by_user}

    # Get voice minutes by user
    voice_by_user = await db.execute(
        select(
            VoiceSession.user_id,
            func.sum(VoiceSession.duration_seconds).label("total_seconds"),
        )
        .where(
            VoiceSession.tenant_id == tenant_id,
            VoiceSession.started_at >= since,
            VoiceSession.user_id != None,
        )
        .group_by(VoiceSession.user_id)
    )
    voice_data = {row.user_id: int((row.total_seconds or 0) / 60) for row in voice_by_user}

    # Get GitHub activity by user
    github_by_user = await db.execute(
        select(
            GitHubEvent.user_id,
            func.count(case((GitHubEvent.event_type == "commit", 1))).label("commits"),
            func.count(case((GitHubEvent.event_type == "pull_request", 1))).label("prs"),
            func.count(case((GitHubEvent.event_type == "pull_request_review", 1))).label("reviews"),
        )
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
            GitHubEvent.user_id != None,
        )
        .group_by(GitHubEvent.user_id)
    )
    github_data = {row.user_id: {"commits": row.commits, "prs": row.prs, "reviews": row.reviews} for row in github_by_user}

    # Get all user IDs and fetch user info
    all_user_ids = set(discord_data.keys()) | set(voice_data.keys()) | set(github_data.keys())

    if not all_user_ids:
        return []

    users_result = await db.execute(
        select(User).where(User.id.in_(all_user_ids))
    )
    users = {u.id: u for u in users_result.scalars().all()}

    # Build response
    summaries = []
    for user_id in all_user_ids:
        user = users.get(user_id)
        gh_data = github_data.get(user_id, {"commits": 0, "prs": 0, "reviews": 0})
        summaries.append(UserActivitySummary(
            user_id=user_id,
            discord_username=user.discord_username if user else None,
            github_username=user.github_username if user else None,
            discord_messages=discord_data.get(user_id, 0),
            discord_voice_minutes=voice_data.get(user_id, 0),
            github_commits=gh_data["commits"],
            github_prs=gh_data["prs"],
            github_reviews=gh_data["reviews"],
        ))

    # Sort by total activity
    summaries.sort(key=lambda x: x.discord_messages + x.github_commits + x.github_prs, reverse=True)
    return summaries


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    """Get detailed activity for a specific user."""
    logger.info(
        "Getting user detail",
        tenant_id=tenant_id,
        user_id=user_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get user info
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    # Get Discord activity
    discord_result = await db.execute(
        select(
            cast(DiscordEvent.created_at, Date).label("date"),
            func.count(DiscordEvent.id).label("count"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.user_id == user_id,
            DiscordEvent.created_at >= since,
        )
        .group_by(cast(DiscordEvent.created_at, Date))
        .order_by(cast(DiscordEvent.created_at, Date))
    )
    discord_activity = [{"date": str(row.date), "count": row.count} for row in discord_result]

    # Get GitHub activity
    github_result = await db.execute(
        select(
            cast(GitHubEvent.created_at, Date).label("date"),
            GitHubEvent.event_type,
            func.count(GitHubEvent.id).label("count"),
        )
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.user_id == user_id,
            GitHubEvent.created_at >= since,
        )
        .group_by(cast(GitHubEvent.created_at, Date), GitHubEvent.event_type)
        .order_by(cast(GitHubEvent.created_at, Date))
    )
    github_activity = [{"date": str(row.date), "type": row.event_type, "count": row.count} for row in github_result]

    return {
        "user_id": user_id,
        "discord_username": user.discord_username if user else None,
        "github_username": user.github_username if user else None,
        "discord_activity": discord_activity,
        "github_activity": github_activity,
    }


@router.get("/correlations")
async def get_correlations(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> list[CorrelationInsight]:
    """Get Discord-GitHub correlation insights."""
    logger.info(
        "Getting correlations",
        tenant_id=tenant_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get users who are active on both platforms
    discord_users = await db.execute(
        select(DiscordEvent.user_id, func.count(DiscordEvent.id).label("discord_count"))
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
            DiscordEvent.user_id != None,
        )
        .group_by(DiscordEvent.user_id)
    )
    discord_by_user = {row.user_id: row.discord_count for row in discord_users}

    github_users = await db.execute(
        select(GitHubEvent.user_id, func.count(GitHubEvent.id).label("github_count"))
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
            GitHubEvent.user_id != None,
        )
        .group_by(GitHubEvent.user_id)
    )
    github_by_user = {row.user_id: row.github_count for row in github_users}

    # Find users active on both platforms
    both_users = set(discord_by_user.keys()) & set(github_by_user.keys())

    insights = []

    if both_users:
        total_discord = sum(discord_by_user.get(u, 0) for u in both_users)
        total_github = sum(github_by_user.get(u, 0) for u in both_users)

        # Determine correlation strength based on activity balance
        ratio = total_discord / max(total_github, 1)
        if 0.5 <= ratio <= 2.0:
            strength = "high"
            summary = "Team shows balanced engagement across Discord and GitHub."
        elif 0.2 <= ratio <= 5.0:
            strength = "medium"
            summary = "Some imbalance between communication and development activity."
        else:
            strength = "low"
            summary = "Significant gap between communication and development platforms."

        insights.append(CorrelationInsight(
            topic="Cross-Platform Engagement",
            discord_mentions=total_discord,
            github_activity=total_github,
            correlation_strength=strength,
            summary=summary,
        ))

    return insights


@router.get("/discord")
async def get_discord_analytics(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
    channel_ids: Optional[List[int]] = Query(default=None),
) -> dict[str, Any]:
    """Get detailed Discord analytics."""
    logger.info(
        "Getting Discord analytics",
        tenant_id=tenant_id,
        days=days,
        channel_ids=channel_ids,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_query = select(DiscordEvent).where(
        DiscordEvent.tenant_id == tenant_id,
        DiscordEvent.created_at >= since,
    )
    if channel_ids:
        base_query = base_query.where(DiscordEvent.channel_id.in_(channel_ids))

    # Total messages
    total_result = await db.execute(
        select(func.count(DiscordEvent.id))
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
        )
    )
    total_messages = total_result.scalar() or 0

    # Messages by channel
    channel_result = await db.execute(
        select(
            DiscordEvent.channel_id,
            func.count(DiscordEvent.id).label("count"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
        )
        .group_by(DiscordEvent.channel_id)
        .order_by(func.count(DiscordEvent.id).desc())
        .limit(10)
    )
    messages_by_channel = [{"channel_id": row.channel_id, "count": row.count} for row in channel_result]

    # Messages by user
    user_result = await db.execute(
        select(
            DiscordEvent.user_id,
            func.count(DiscordEvent.id).label("count"),
        )
        .where(
            DiscordEvent.tenant_id == tenant_id,
            DiscordEvent.created_at >= since,
            DiscordEvent.user_id != None,
        )
        .group_by(DiscordEvent.user_id)
        .order_by(func.count(DiscordEvent.id).desc())
        .limit(10)
    )
    messages_by_user = [{"user_id": row.user_id, "count": row.count} for row in user_result]

    # Voice hours by channel
    voice_result = await db.execute(
        select(
            VoiceSession.channel_id,
            func.sum(VoiceSession.duration_seconds).label("total_seconds"),
        )
        .where(
            VoiceSession.tenant_id == tenant_id,
            VoiceSession.started_at >= since,
        )
        .group_by(VoiceSession.channel_id)
        .order_by(func.sum(VoiceSession.duration_seconds).desc())
        .limit(10)
    )
    voice_hours_by_channel = [
        {"channel_id": row.channel_id, "hours": round((row.total_seconds or 0) / 3600, 1)}
        for row in voice_result
    ]

    return {
        "total_messages": total_messages,
        "messages_by_channel": messages_by_channel,
        "messages_by_user": messages_by_user,
        "voice_hours_by_channel": voice_hours_by_channel,
    }


@router.get("/github")
async def get_github_analytics(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
    repos: Optional[List[str]] = Query(default=None),
) -> dict[str, Any]:
    """Get detailed GitHub analytics."""
    logger.info(
        "Getting GitHub analytics",
        tenant_id=tenant_id,
        days=days,
        repos=repos,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    base_filter = [
        GitHubEvent.tenant_id == tenant_id,
        GitHubEvent.created_at >= since,
    ]
    if repos:
        base_filter.append(GitHubEvent.repo_full_name.in_(repos))

    # Total commits
    commit_result = await db.execute(
        select(func.count(GitHubEvent.id))
        .where(*base_filter, GitHubEvent.event_type == "commit")
    )
    total_commits = commit_result.scalar() or 0

    # Total PRs
    pr_result = await db.execute(
        select(func.count(GitHubEvent.id))
        .where(*base_filter, GitHubEvent.event_type == "pull_request")
    )
    total_prs = pr_result.scalar() or 0

    # Total issues
    issue_result = await db.execute(
        select(func.count(GitHubEvent.id))
        .where(*base_filter, GitHubEvent.event_type == "issue")
    )
    total_issues = issue_result.scalar() or 0

    # Commits by repo
    repo_result = await db.execute(
        select(
            GitHubEvent.repo_full_name,
            func.count(GitHubEvent.id).label("count"),
        )
        .where(*base_filter, GitHubEvent.event_type == "commit")
        .group_by(GitHubEvent.repo_full_name)
        .order_by(func.count(GitHubEvent.id).desc())
        .limit(10)
    )
    commits_by_repo = [{"repo": row.repo_full_name, "count": row.count} for row in repo_result]

    # Commits by user
    user_result = await db.execute(
        select(
            GitHubEvent.github_user_login,
            func.count(GitHubEvent.id).label("count"),
        )
        .where(*base_filter, GitHubEvent.event_type == "commit")
        .group_by(GitHubEvent.github_user_login)
        .order_by(func.count(GitHubEvent.id).desc())
        .limit(10)
    )
    commits_by_user = [{"user": row.github_user_login, "count": row.count} for row in user_result]

    return {
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_issues": total_issues,
        "commits_by_repo": commits_by_repo,
        "commits_by_user": commits_by_user,
    }
