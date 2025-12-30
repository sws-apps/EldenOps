"""GitHub-related background tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional,  Any

from sqlalchemy import select, func, update
import structlog

from eldenops.ai.router import analyze_with_ai
from eldenops.db.engine import get_session
from eldenops.db.models.github import GitHubEvent, GitHubConnection
from eldenops.db.models.user import User
from eldenops.integrations.github.client import GitHubClient

logger = structlog.get_logger()


async def process_github_event(
    ctx: dict,
    tenant_id: str,
    connection_id: str,
    event_data: dict[str, Any],
) -> dict[str, Any]:
    """Process a GitHub webhook event and store it in the database.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        connection_id: GitHub connection ID
        event_data: Parsed event data from webhook

    Returns:
        Processing result
    """
    event_type = event_data.get("event_type")
    logger.info(
        "Processing GitHub event",
        tenant_id=tenant_id,
        connection_id=connection_id,
        event_type=event_type,
    )

    events_created = 0

    async with get_session() as db:
        # Look up user by GitHub username if provided
        async def get_user_id(github_login: Optional[str]) -> Optional[str]:
            if not github_login:
                return None
            result = await db.execute(
                select(User).where(User.github_username == github_login)
            )
            user = result.scalar_one_or_none()
            return user.id if user else None

        repo_full_name = event_data.get("repo_full_name", "")

        # For push events with multiple commits
        if event_type == "push":
            commits = event_data.get("commits", [])
            logger.info(f"Processing {len(commits)} commits")

            for commit in commits:
                user_id = await get_user_id(commit.get("author", {}).get("username"))

                github_event = GitHubEvent(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    user_id=user_id,
                    github_user_login=commit.get("author", {}).get("username"),
                    event_type="commit",
                    repo_full_name=repo_full_name,
                    ref_id=commit.get("id"),
                    ref_url=commit.get("url"),
                    title=commit.get("message", "")[:200],
                    body_preview=commit.get("message", "")[:500],
                    additions=commit.get("added_lines"),
                    deletions=commit.get("removed_lines"),
                    files_changed=len(commit.get("modified", [])) + len(commit.get("added", [])) + len(commit.get("removed", [])),
                    metadata={"branch": event_data.get("ref", "").replace("refs/heads/", "")},
                    created_at=datetime.fromisoformat(commit.get("timestamp", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")),
                )
                db.add(github_event)
                events_created += 1

        # For PR events
        elif event_type in ("pull_request", "pull_request_review"):
            pr = event_data.get("pull_request", {})
            user_id = await get_user_id(pr.get("user", {}).get("login"))

            github_event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                user_id=user_id,
                github_user_login=pr.get("user", {}).get("login"),
                github_user_id=pr.get("user", {}).get("id"),
                event_type=event_type,
                repo_full_name=repo_full_name,
                ref_id=str(pr.get("number")),
                ref_url=pr.get("html_url"),
                title=pr.get("title"),
                body_preview=pr.get("body", "")[:500] if pr.get("body") else None,
                additions=pr.get("additions"),
                deletions=pr.get("deletions"),
                files_changed=pr.get("changed_files"),
                metadata={"action": event_data.get("action"), "state": pr.get("state")},
                created_at=datetime.now(timezone.utc),
            )
            db.add(github_event)
            events_created += 1

        # For issue events
        elif event_type == "issues":
            issue = event_data.get("issue", {})
            user_id = await get_user_id(issue.get("user", {}).get("login"))

            github_event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                user_id=user_id,
                github_user_login=issue.get("user", {}).get("login"),
                github_user_id=issue.get("user", {}).get("id"),
                event_type="issue",
                repo_full_name=repo_full_name,
                ref_id=str(issue.get("number")),
                ref_url=issue.get("html_url"),
                title=issue.get("title"),
                body_preview=issue.get("body", "")[:500] if issue.get("body") else None,
                metadata={"action": event_data.get("action"), "state": issue.get("state")},
                created_at=datetime.now(timezone.utc),
            )
            db.add(github_event)
            events_created += 1

        # Generic event for other types
        else:
            sender = event_data.get("sender", {})
            user_id = await get_user_id(sender.get("login"))

            github_event = GitHubEvent(
                tenant_id=tenant_id,
                connection_id=connection_id,
                user_id=user_id,
                github_user_login=sender.get("login"),
                github_user_id=sender.get("id"),
                event_type=event_type,
                repo_full_name=repo_full_name,
                metadata={"action": event_data.get("action")},
                created_at=datetime.now(timezone.utc),
            )
            db.add(github_event)
            events_created += 1

    logger.info(
        "GitHub events stored",
        tenant_id=tenant_id,
        events_created=events_created,
    )

    return {
        "status": "processed",
        "tenant_id": tenant_id,
        "event_type": event_type,
        "events_created": events_created,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


async def sync_github_repo(
    ctx: dict,
    tenant_id: str,
    connection_id: str,
    repo_full_name: str,
    github_token: str,
    days: int = 30,
) -> dict[str, Any]:
    """Sync historical data from a GitHub repository.

    Called when a new repo is connected to fetch historical commits, PRs, etc.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        connection_id: GitHub connection ID
        repo_full_name: Repository in owner/repo format
        github_token: GitHub access token
        days: Number of days of history to sync

    Returns:
        Sync results
    """
    logger.info(
        "Syncing GitHub repo",
        tenant_id=tenant_id,
        repo=repo_full_name,
        days=days,
    )

    owner, repo = repo_full_name.split("/")
    client = GitHubClient(github_token)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    commits_synced = 0
    prs_synced = 0
    issues_synced = 0

    try:
        async with get_session() as db:
            # Fetch and store commits
            commits = await client.get_commits(owner, repo, per_page=100)
            for commit in commits:
                commit_date = datetime.fromisoformat(
                    commit.get("commit", {}).get("author", {}).get("date", "").replace("Z", "+00:00")
                )
                if commit_date < since:
                    continue

                github_event = GitHubEvent(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    github_user_login=commit.get("author", {}).get("login") if commit.get("author") else None,
                    github_user_id=commit.get("author", {}).get("id") if commit.get("author") else None,
                    event_type="commit",
                    repo_full_name=repo_full_name,
                    ref_id=commit.get("sha"),
                    ref_url=commit.get("html_url"),
                    title=commit.get("commit", {}).get("message", "")[:200],
                    body_preview=commit.get("commit", {}).get("message", "")[:500],
                    metadata={"synced": True},
                    created_at=commit_date,
                )
                db.add(github_event)
                commits_synced += 1

            # Fetch and store PRs
            prs = await client.get_pull_requests(owner, repo, state="all", per_page=100)
            for pr in prs:
                pr_date = datetime.fromisoformat(pr.get("created_at", "").replace("Z", "+00:00"))
                if pr_date < since:
                    continue

                github_event = GitHubEvent(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    github_user_login=pr.get("user", {}).get("login"),
                    github_user_id=pr.get("user", {}).get("id"),
                    event_type="pull_request",
                    repo_full_name=repo_full_name,
                    ref_id=str(pr.get("number")),
                    ref_url=pr.get("html_url"),
                    title=pr.get("title"),
                    body_preview=pr.get("body", "")[:500] if pr.get("body") else None,
                    metadata={"state": pr.get("state"), "synced": True},
                    created_at=pr_date,
                )
                db.add(github_event)
                prs_synced += 1

            # Fetch and store issues
            issues = await client.get_issues(owner, repo, state="all", per_page=100)
            for issue in issues:
                # Skip PRs (they show up in issues too)
                if issue.get("pull_request"):
                    continue

                issue_date = datetime.fromisoformat(issue.get("created_at", "").replace("Z", "+00:00"))
                if issue_date < since:
                    continue

                github_event = GitHubEvent(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    github_user_login=issue.get("user", {}).get("login"),
                    github_user_id=issue.get("user", {}).get("id"),
                    event_type="issue",
                    repo_full_name=repo_full_name,
                    ref_id=str(issue.get("number")),
                    ref_url=issue.get("html_url"),
                    title=issue.get("title"),
                    body_preview=issue.get("body", "")[:500] if issue.get("body") else None,
                    metadata={"state": issue.get("state"), "synced": True},
                    created_at=issue_date,
                )
                db.add(github_event)
                issues_synced += 1

            # Update connection's last_synced_at
            await db.execute(
                update(GitHubConnection)
                .where(GitHubConnection.id == connection_id)
                .values(last_synced_at=datetime.now(timezone.utc))
            )

        logger.info(
            "GitHub repo sync completed",
            repo=repo_full_name,
            commits=commits_synced,
            prs=prs_synced,
            issues=issues_synced,
        )

        return {
            "status": "completed",
            "tenant_id": tenant_id,
            "repo": repo_full_name,
            "commits_synced": commits_synced,
            "prs_synced": prs_synced,
            "issues_synced": issues_synced,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    finally:
        await client.close()


async def summarize_github_activity(
    ctx: dict,
    tenant_id: str,
    repo_full_name: str,
    days: int = 7,
) -> dict[str, Any]:
    """Generate AI summary of GitHub activity.

    Args:
        ctx: ARQ context
        tenant_id: The tenant ID
        repo_full_name: Repository to summarize
        days: Number of days to analyze

    Returns:
        Summary results
    """
    logger.info(
        "Summarizing GitHub activity",
        tenant_id=tenant_id,
        repo=repo_full_name,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_session() as db:
        # Fetch events from database
        result = await db.execute(
            select(GitHubEvent)
            .where(
                GitHubEvent.tenant_id == tenant_id,
                GitHubEvent.repo_full_name == repo_full_name,
                GitHubEvent.created_at >= since,
            )
            .order_by(GitHubEvent.created_at.desc())
        )
        events = result.scalars().all()

        # Get aggregate stats
        stats_result = await db.execute(
            select(
                func.count(GitHubEvent.id).label("total_events"),
                func.count(func.distinct(GitHubEvent.github_user_login)).label("unique_contributors"),
                func.sum(GitHubEvent.additions).label("total_additions"),
                func.sum(GitHubEvent.deletions).label("total_deletions"),
            )
            .where(
                GitHubEvent.tenant_id == tenant_id,
                GitHubEvent.repo_full_name == repo_full_name,
                GitHubEvent.created_at >= since,
            )
        )
        stats = stats_result.one()

    if not events:
        return {
            "status": "completed",
            "repo": repo_full_name,
            "summary": "No activity found for this period.",
            "stats": {"total_events": 0, "unique_contributors": 0},
        }

    # Build summary for AI
    event_summary = f"""
GitHub Repository Activity Summary for {repo_full_name} (last {days} days):
- Total events: {stats.total_events}
- Unique contributors: {stats.unique_contributors}
- Lines added: {stats.total_additions or 0}
- Lines deleted: {stats.total_deletions or 0}

Event types breakdown:
"""
    # Count by event type
    type_counts: dict[str, int] = {}
    for event in events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    for event_type, count in type_counts.items():
        event_summary += f"- {event_type}: {count}\n"

    # Add recent notable events
    event_summary += "\nRecent notable events:\n"
    for event in events[:10]:  # Top 10 most recent
        if event.title:
            event_summary += f"- [{event.event_type}] {event.title[:80]}\n"

    # Send to AI for summarization
    ai_response = await analyze_with_ai(
        prompt=f"""Summarize this GitHub repository activity and provide insights:

{event_summary}

Please provide:
1. Summary of development activity
2. Key contributions and changes
3. Notable PRs or issues
4. Team velocity assessment
""",
        system_prompt="You are a software development analytics assistant. Provide concise, technical summaries of repository activity.",
        max_tokens=1024,
        temperature=0.5,
    )

    return {
        "status": "completed",
        "repo": repo_full_name,
        "summary": ai_response.content,
        "stats": {
            "total_events": stats.total_events,
            "unique_contributors": stats.unique_contributors,
            "total_additions": stats.total_additions or 0,
            "total_deletions": stats.total_deletions or 0,
        },
        "tokens_used": ai_response.usage.total_tokens if ai_response.usage else None,
    }
