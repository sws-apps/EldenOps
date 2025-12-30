"""GitHub webhook handler."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional,  Any

import structlog

from eldenops.config.constants import GitHubEventType
from eldenops.core.exceptions import GitHubIntegrationError

logger = structlog.get_logger()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not signature.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)


def parse_webhook_event(
    event_type: str, payload: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Parse a GitHub webhook event into our format.

    Args:
        event_type: GitHub event type (X-GitHub-Event header)
        payload: Webhook payload

    Returns:
        Parsed event data or None if event should be ignored
    """
    handlers = {
        "push": _parse_push_event,
        "pull_request": _parse_pull_request_event,
        "issues": _parse_issues_event,
        "issue_comment": _parse_issue_comment_event,
        "pull_request_review": _parse_pr_review_event,
    }

    handler = handlers.get(event_type)
    if handler is None:
        logger.debug("Ignoring unhandled webhook event", event_type=event_type)
        return None

    try:
        return handler(payload)
    except Exception as e:
        logger.error(
            "Failed to parse webhook event",
            event_type=event_type,
            error=str(e),
        )
        raise GitHubIntegrationError(f"Failed to parse {event_type} event: {e}") from e


def _parse_push_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse a push event (commits)."""
    repo = payload["repository"]
    commits = payload.get("commits", [])

    # Parse each commit
    parsed_commits = []
    for commit in commits:
        parsed_commits.append({
            "event_type": GitHubEventType.COMMIT,
            "repo_full_name": repo["full_name"],
            "ref_id": commit["id"],
            "ref_url": commit["url"],
            "title": commit["message"].split("\n")[0][:255],  # First line, truncated
            "body_preview": commit["message"][:500] if commit["message"] else None,
            "github_user_login": commit["author"].get("username"),
            "github_user_email": commit["author"].get("email"),
            "timestamp": commit["timestamp"],
            "additions": commit.get("added", []),
            "deletions": commit.get("removed", []),
            "files_changed": len(commit.get("modified", [])) + len(commit.get("added", [])) + len(commit.get("removed", [])),
        })

    return {
        "event_type": "push",
        "repo_full_name": repo["full_name"],
        "ref": payload.get("ref"),
        "commits": parsed_commits,
        "pusher": payload.get("pusher", {}).get("name"),
    }


def _parse_pull_request_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse a pull request event."""
    action = payload["action"]
    pr = payload["pull_request"]
    repo = payload["repository"]

    # Map action to our event type
    event_type_map = {
        "opened": GitHubEventType.PR_OPENED,
        "closed": GitHubEventType.PR_MERGED if pr.get("merged") else GitHubEventType.PR_CLOSED,
        "reopened": GitHubEventType.PR_OPENED,
    }

    event_type = event_type_map.get(action)
    if event_type is None:
        return {"skip": True, "reason": f"PR action {action} not tracked"}

    return {
        "event_type": event_type,
        "repo_full_name": repo["full_name"],
        "ref_id": str(pr["number"]),
        "ref_url": pr["html_url"],
        "title": pr["title"],
        "body_preview": pr.get("body", "")[:500] if pr.get("body") else None,
        "github_user_login": pr["user"]["login"],
        "github_user_id": pr["user"]["id"],
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "files_changed": pr.get("changed_files", 0),
        "merged_at": pr.get("merged_at"),
        "created_at": pr["created_at"],
    }


def _parse_issues_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse an issues event."""
    action = payload["action"]
    issue = payload["issue"]
    repo = payload["repository"]

    # Skip PR issues (they have a pull_request key)
    if "pull_request" in issue:
        return {"skip": True, "reason": "Issue is a PR"}

    event_type_map = {
        "opened": GitHubEventType.ISSUE_OPENED,
        "closed": GitHubEventType.ISSUE_CLOSED,
        "reopened": GitHubEventType.ISSUE_OPENED,
    }

    event_type = event_type_map.get(action)
    if event_type is None:
        return {"skip": True, "reason": f"Issue action {action} not tracked"}

    return {
        "event_type": event_type,
        "repo_full_name": repo["full_name"],
        "ref_id": str(issue["number"]),
        "ref_url": issue["html_url"],
        "title": issue["title"],
        "body_preview": issue.get("body", "")[:500] if issue.get("body") else None,
        "github_user_login": issue["user"]["login"],
        "github_user_id": issue["user"]["id"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "created_at": issue["created_at"],
        "closed_at": issue.get("closed_at"),
    }


def _parse_issue_comment_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse an issue comment event."""
    action = payload["action"]
    if action != "created":
        return {"skip": True, "reason": f"Comment action {action} not tracked"}

    comment = payload["comment"]
    issue = payload["issue"]
    repo = payload["repository"]

    # Determine if this is a PR comment or issue comment
    is_pr = "pull_request" in issue
    event_type = GitHubEventType.PR_COMMENT if is_pr else GitHubEventType.ISSUE_COMMENT

    return {
        "event_type": event_type,
        "repo_full_name": repo["full_name"],
        "ref_id": str(issue["number"]),
        "ref_url": comment["html_url"],
        "title": f"Comment on #{issue['number']}: {issue['title'][:100]}",
        "body_preview": comment.get("body", "")[:500] if comment.get("body") else None,
        "github_user_login": comment["user"]["login"],
        "github_user_id": comment["user"]["id"],
        "created_at": comment["created_at"],
    }


def _parse_pr_review_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse a pull request review event."""
    action = payload["action"]
    if action != "submitted":
        return {"skip": True, "reason": f"Review action {action} not tracked"}

    review = payload["review"]
    pr = payload["pull_request"]
    repo = payload["repository"]

    return {
        "event_type": GitHubEventType.PR_REVIEW,
        "repo_full_name": repo["full_name"],
        "ref_id": str(pr["number"]),
        "ref_url": review["html_url"],
        "title": f"Review on PR #{pr['number']}: {pr['title'][:100]}",
        "body_preview": review.get("body", "")[:500] if review.get("body") else None,
        "github_user_login": review["user"]["login"],
        "github_user_id": review["user"]["id"],
        "review_state": review["state"],  # approved, changes_requested, commented
        "created_at": review["submitted_at"],
    }
