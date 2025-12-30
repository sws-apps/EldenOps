"""GitHub analytics API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, case
import structlog

from eldenops.api.deps import CurrentUser, DBSession, TenantID
from eldenops.db.models.github import GitHubEvent, GitHubConnection
from eldenops.db.models.tenant import Tenant
from eldenops.core.security import decrypt_api_key
from eldenops.integrations.github.client import GitHubClient
from eldenops.core.exceptions import GitHubIntegrationError

logger = structlog.get_logger()
router = APIRouter()


class RepoSummary(BaseModel):
    """Repository summary."""
    repo_full_name: str
    total_commits: int
    total_prs: int
    total_issues: int
    contributors: int
    lines_added: int
    lines_deleted: int


class GitHubSummaryResponse(BaseModel):
    """GitHub activity summary response."""
    period_days: int
    repos: list[RepoSummary]
    totals: dict[str, int]


class ContributorStats(BaseModel):
    """Contributor statistics."""
    github_username: str
    commits: int
    prs_opened: int
    prs_merged: int
    issues_opened: int
    lines_added: int
    lines_deleted: int


class GitHubInsightsResponse(BaseModel):
    """GitHub behavioral insights response."""
    period_days: int
    has_data: bool
    message: Optional[str] = None
    commit_patterns: Optional[dict[str, Any]] = None
    pr_patterns: Optional[dict[str, Any]] = None
    top_contributors: Optional[list[ContributorStats]] = None
    activity_by_day: Optional[dict[str, int]] = None
    activity_by_hour: Optional[dict[str, int]] = None


class AddConnectionRequest(BaseModel):
    """Request to add a GitHub connection."""
    repo_full_name: str  # Format: owner/repo


class ConnectionResponse(BaseModel):
    """GitHub connection response."""
    id: str
    repo_full_name: str
    org_name: Optional[str]
    repo_name: str
    last_synced_at: Optional[str]
    is_active: bool


@router.get("/connections")
async def get_github_connections(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[ConnectionResponse]:
    """Get all GitHub connections for the tenant."""
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.is_active == True,
        )
    )
    connections = result.scalars().all()

    return [
        ConnectionResponse(
            id=str(conn.id),
            repo_full_name=conn.repo_full_name,
            org_name=conn.org_name,
            repo_name=conn.repo_name,
            last_synced_at=conn.last_synced_at.isoformat() if conn.last_synced_at else None,
            is_active=conn.is_active,
        )
        for conn in connections
    ]


@router.post("/connections")
async def add_github_connection(
    request: AddConnectionRequest,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> ConnectionResponse:
    """Add a GitHub repository connection."""
    # Parse repo name
    parts = request.repo_full_name.strip().split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid repo format. Use owner/repo")

    org_name, repo_name = parts
    repo_full_name = f"{org_name}/{repo_name}"

    # Get tenant's GitHub token
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant or not tenant.github_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail="GitHub token not configured. Please add your GitHub token in Settings first."
        )

    # Decrypt token and validate repo exists
    try:
        github_token = decrypt_api_key(tenant.github_token_encrypted)
        client = GitHubClient(github_token)

        # Validate repo exists and is accessible
        try:
            await client.get_repo(org_name, repo_name)
        except GitHubIntegrationError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot access repository '{repo_full_name}'. Please check the repository exists and your token has access."
            )
        finally:
            await client.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error validating GitHub repo", error=str(e))
        raise HTTPException(status_code=500, detail="Error validating repository")

    # Check if already connected
    existing = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.repo_full_name == repo_full_name,
            GitHubConnection.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Repository already connected")

    # Create connection
    connection = GitHubConnection(
        tenant_id=tenant_id,
        connected_by_user_id=current_user.get("user_id"),
        org_name=org_name,
        repo_name=repo_name,
        repo_full_name=repo_full_name,
        is_active=True,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    logger.info("GitHub connection added", repo=repo_full_name, tenant_id=tenant_id)

    # TODO: Trigger background sync task to fetch historical data
    # This would use ARQ or similar task queue:
    # await arq_pool.enqueue_job('sync_github_repo', tenant_id, str(connection.id), repo_full_name, github_token)

    return ConnectionResponse(
        id=str(connection.id),
        repo_full_name=connection.repo_full_name,
        org_name=connection.org_name,
        repo_name=connection.repo_name,
        last_synced_at=None,
        is_active=connection.is_active,
    )


@router.post("/connections/{connection_id}/sync")
async def sync_github_connection(
    connection_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = 30,
) -> dict[str, Any]:
    """Manually sync a GitHub repository to fetch commits, PRs, and issues."""
    # Get connection
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.tenant_id == tenant_id,
            GitHubConnection.is_active == True,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Get tenant's GitHub token
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if not tenant or not tenant.github_token_encrypted:
        raise HTTPException(status_code=400, detail="GitHub token not configured")

    github_token = decrypt_api_key(tenant.github_token_encrypted)
    owner, repo = connection.repo_full_name.split("/")

    client = GitHubClient(github_token)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    commits_synced = 0
    prs_synced = 0
    issues_synced = 0

    try:
        # Fetch commits
        commits = await client.get_commits(owner, repo, since=since, per_page=100)
        for commit in commits:
            # Check if already exists
            existing = await db.execute(
                select(GitHubEvent).where(
                    GitHubEvent.tenant_id == tenant_id,
                    GitHubEvent.ref_id == commit.sha,
                )
            )
            if existing.scalar_one_or_none():
                continue

            event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                github_user_login=commit.author_login,
                event_type="commit",
                repo_full_name=connection.repo_full_name,
                ref_id=commit.sha,
                ref_url=commit.url,
                title=commit.message[:200] if commit.message else None,
                body_preview=commit.message[:500] if commit.message else None,
                additions=commit.additions,
                deletions=commit.deletions,
                files_changed=commit.files_changed,
                created_at=commit.committed_at,
            )
            db.add(event)
            commits_synced += 1

        # Fetch PRs
        prs = await client.get_pull_requests(owner, repo, state="all", per_page=100)
        for pr in prs:
            if pr.created_at < since:
                continue
            # Check if already exists
            existing = await db.execute(
                select(GitHubEvent).where(
                    GitHubEvent.tenant_id == tenant_id,
                    GitHubEvent.event_type == "pull_request",
                    GitHubEvent.ref_id == str(pr.number),
                    GitHubEvent.repo_full_name == connection.repo_full_name,
                )
            )
            if existing.scalar_one_or_none():
                continue

            event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                github_user_login=pr.author_login,
                event_type="pull_request",
                repo_full_name=connection.repo_full_name,
                ref_id=str(pr.number),
                ref_url=pr.url,
                title=pr.title,
                body_preview=pr.body[:500] if pr.body else None,
                additions=pr.additions,
                deletions=pr.deletions,
                files_changed=pr.changed_files,
                event_metadata={"state": pr.state, "merged_at": pr.merged_at.isoformat() if pr.merged_at else None},
                created_at=pr.created_at,
            )
            db.add(event)
            prs_synced += 1

        # Fetch issues
        issues = await client.get_issues(owner, repo, state="all", per_page=100)
        for issue in issues:
            if issue.created_at < since:
                continue
            # Check if already exists
            existing = await db.execute(
                select(GitHubEvent).where(
                    GitHubEvent.tenant_id == tenant_id,
                    GitHubEvent.event_type == "issue",
                    GitHubEvent.ref_id == str(issue.number),
                    GitHubEvent.repo_full_name == connection.repo_full_name,
                )
            )
            if existing.scalar_one_or_none():
                continue

            event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                github_user_login=issue.author_login,
                event_type="issue",
                repo_full_name=connection.repo_full_name,
                ref_id=str(issue.number),
                ref_url=issue.url,
                title=issue.title,
                body_preview=issue.body[:500] if issue.body else None,
                event_metadata={"state": issue.state, "labels": issue.labels},
                created_at=issue.created_at,
            )
            db.add(event)
            issues_synced += 1

        # Update last synced timestamp
        connection.last_synced_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "GitHub sync completed",
            repo=connection.repo_full_name,
            commits=commits_synced,
            prs=prs_synced,
            issues=issues_synced,
        )

        return {
            "status": "completed",
            "repo": connection.repo_full_name,
            "commits_synced": commits_synced,
            "prs_synced": prs_synced,
            "issues_synced": issues_synced,
        }

    except GitHubIntegrationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.close()


@router.delete("/connections/{connection_id}")
async def remove_github_connection(
    connection_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, str]:
    """Remove a GitHub repository connection."""
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Connection not found")

    # Soft delete - mark as inactive
    connection.is_active = False
    await db.commit()

    logger.info("GitHub connection removed", repo=connection.repo_full_name, tenant_id=tenant_id)

    return {"message": "Connection removed"}


@router.get("/summary")
async def get_github_summary(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> GitHubSummaryResponse:
    """Get GitHub activity summary for all connected repos."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get per-repo stats
    result = await db.execute(
        select(
            GitHubEvent.repo_full_name,
            func.count(case((GitHubEvent.event_type == "commit", 1))).label("commits"),
            func.count(case((GitHubEvent.event_type == "pull_request", 1))).label("prs"),
            func.count(case((GitHubEvent.event_type == "issue", 1))).label("issues"),
            func.count(func.distinct(GitHubEvent.github_user_login)).label("contributors"),
            func.coalesce(func.sum(GitHubEvent.additions), 0).label("additions"),
            func.coalesce(func.sum(GitHubEvent.deletions), 0).label("deletions"),
        )
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
        )
        .group_by(GitHubEvent.repo_full_name)
    )
    rows = result.all()

    repos = []
    totals = {
        "commits": 0,
        "prs": 0,
        "issues": 0,
        "contributors": 0,
        "lines_added": 0,
        "lines_deleted": 0,
    }

    for row in rows:
        repos.append(RepoSummary(
            repo_full_name=row.repo_full_name,
            total_commits=row.commits,
            total_prs=row.prs,
            total_issues=row.issues,
            contributors=row.contributors,
            lines_added=row.additions or 0,
            lines_deleted=row.deletions or 0,
        ))
        totals["commits"] += row.commits
        totals["prs"] += row.prs
        totals["issues"] += row.issues
        totals["lines_added"] += row.additions or 0
        totals["lines_deleted"] += row.deletions or 0

    # Get unique contributors across all repos
    unique_result = await db.execute(
        select(func.count(func.distinct(GitHubEvent.github_user_login)))
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
        )
    )
    totals["contributors"] = unique_result.scalar() or 0

    return GitHubSummaryResponse(
        period_days=days,
        repos=repos,
        totals=totals,
    )


@router.get("/insights")
async def get_github_insights(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=30, ge=7, le=90),
) -> GitHubInsightsResponse:
    """Get behavioral insights from GitHub activity."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all events
    result = await db.execute(
        select(GitHubEvent)
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
        )
        .order_by(GitHubEvent.created_at)
    )
    events = result.scalars().all()

    if not events:
        return GitHubInsightsResponse(
            period_days=days,
            has_data=False,
            message="No GitHub activity for this period",
        )

    # Analyze patterns
    commit_hours: dict[int, int] = {}
    pr_hours: dict[int, int] = {}
    day_counts: dict[str, int] = {}
    hour_counts: dict[int, int] = {}

    contributor_stats: dict[str, dict] = {}

    for event in events:
        hour = event.created_at.hour
        day_name = event.created_at.strftime("%A")

        # Activity by day
        day_counts[day_name] = day_counts.get(day_name, 0) + 1

        # Activity by hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1

        # Track contributor stats
        username = event.github_user_login or "unknown"
        if username not in contributor_stats:
            contributor_stats[username] = {
                "commits": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "issues_opened": 0,
                "lines_added": 0,
                "lines_deleted": 0,
            }

        if event.event_type == "commit":
            commit_hours[hour] = commit_hours.get(hour, 0) + 1
            contributor_stats[username]["commits"] += 1
            contributor_stats[username]["lines_added"] += event.additions or 0
            contributor_stats[username]["lines_deleted"] += event.deletions or 0

        elif event.event_type == "pull_request":
            pr_hours[hour] = pr_hours.get(hour, 0) + 1
            action = event.event_metadata.get("action") if event.event_metadata else None
            if action == "opened":
                contributor_stats[username]["prs_opened"] += 1
            elif action == "closed" and event.event_metadata.get("state") == "merged":
                contributor_stats[username]["prs_merged"] += 1

        elif event.event_type == "issue":
            action = event.event_metadata.get("action") if event.event_metadata else None
            if action == "opened":
                contributor_stats[username]["issues_opened"] += 1

    # Calculate peak times
    def get_peak_hour(hour_dist: dict[int, int]) -> Optional[str]:
        if not hour_dist:
            return None
        peak = max(hour_dist.items(), key=lambda x: x[1])
        return f"{peak[0]:02d}:00"

    def calc_avg_hour(hour_dist: dict[int, int]) -> Optional[str]:
        if not hour_dist:
            return None
        total_weight = sum(h * c for h, c in hour_dist.items())
        total_count = sum(hour_dist.values())
        if total_count == 0:
            return None
        avg_hour = total_weight / total_count
        return f"{int(avg_hour):02d}:{int((avg_hour % 1) * 60):02d}"

    # Sort contributors by total activity
    sorted_contributors = sorted(
        contributor_stats.items(),
        key=lambda x: x[1]["commits"] + x[1]["prs_opened"] + x[1]["issues_opened"],
        reverse=True
    )[:10]

    top_contributors = [
        ContributorStats(
            github_username=username,
            commits=stats["commits"],
            prs_opened=stats["prs_opened"],
            prs_merged=stats["prs_merged"],
            issues_opened=stats["issues_opened"],
            lines_added=stats["lines_added"],
            lines_deleted=stats["lines_deleted"],
        )
        for username, stats in sorted_contributors
    ]

    # Order days
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ordered_days = {day: day_counts.get(day, 0) for day in day_order}

    return GitHubInsightsResponse(
        period_days=days,
        has_data=True,
        commit_patterns={
            "peak_hour": get_peak_hour(commit_hours),
            "average_hour": calc_avg_hour(commit_hours),
            "hour_distribution": {f"{h:02d}:00": c for h, c in sorted(commit_hours.items())},
            "total": sum(commit_hours.values()),
        },
        pr_patterns={
            "peak_hour": get_peak_hour(pr_hours),
            "average_hour": calc_avg_hour(pr_hours),
            "hour_distribution": {f"{h:02d}:00": c for h, c in sorted(pr_hours.items())},
            "total": sum(pr_hours.values()),
        },
        top_contributors=top_contributors,
        activity_by_day=ordered_days,
        activity_by_hour={f"{h:02d}:00": hour_counts.get(h, 0) for h in range(24)},
    )


@router.get("/activity")
async def get_github_activity(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Get recent GitHub activity events."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(GitHubEvent)
        .where(
            GitHubEvent.tenant_id == tenant_id,
            GitHubEvent.created_at >= since,
        )
        .order_by(GitHubEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()

    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "repo_full_name": event.repo_full_name,
            "github_user": event.github_user_login,
            "title": event.title,
            "ref_id": event.ref_id,
            "ref_url": event.ref_url,
            "additions": event.additions,
            "deletions": event.deletions,
            "files_changed": event.files_changed,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
