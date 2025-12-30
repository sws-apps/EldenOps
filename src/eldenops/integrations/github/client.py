"""GitHub API client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List,  Optional,  Any

import httpx
import structlog

from eldenops.core.exceptions import GitHubIntegrationError

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class GitHubCommit:
    """Represents a GitHub commit."""

    sha: str
    message: str
    author_login: str
    author_name: str
    author_email: str
    committed_at: datetime
    additions: int
    deletions: int
    files_changed: int
    url: str


@dataclass
class GitHubPullRequest:
    """Represents a GitHub pull request."""

    number: int
    title: str
    body: Optional[str]
    state: str  # open, closed, merged
    author_login: str
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime]
    additions: int
    deletions: int
    changed_files: int
    url: str


@dataclass
class GitHubIssue:
    """Represents a GitHub issue."""

    number: int
    title: str
    body: Optional[str]
    state: str  # open, closed
    author_login: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    labels: list[str]
    url: str


class GitHubClient:
    """Async GitHub API client."""

    def __init__(self, token: str) -> None:
        """Initialize the GitHub client.

        Args:
            token: GitHub personal access token or app token
        """
        self._token = token
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any]:
        """Make an API request."""
        try:
            response = await self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "GitHub API error",
                status=e.response.status_code,
                path=path,
                error=e.response.text,
            )
            raise GitHubIntegrationError(
                f"GitHub API error: {e.response.status_code}",
                details={"path": path, "status": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            logger.error("GitHub request error", path=path, error=str(e))
            raise GitHubIntegrationError(f"GitHub request failed: {e}") from e

    async def validate_token(self) -> bool:
        """Validate the GitHub token."""
        try:
            await self._request("GET", "/user")
            return True
        except GitHubIntegrationError:
            return False

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository information."""
        data = await self._request("GET", f"/repos/{owner}/{repo}")
        return data  # type: ignore

    async def get_commits(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 100,
    ) -> list[GitHubCommit]:
        """Get commits for a repository."""
        params: dict[str, Any] = {"per_page": per_page}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        data = await self._request(
            "GET", f"/repos/{owner}/{repo}/commits", params=params
        )

        commits = []
        for item in data:  # type: ignore
            # Get detailed commit info for additions/deletions
            commit_detail = await self._request(
                "GET", f"/repos/{owner}/{repo}/commits/{item['sha']}"
            )

            commits.append(
                GitHubCommit(
                    sha=item["sha"],
                    message=item["commit"]["message"],
                    author_login=item["author"]["login"] if item.get("author") else "unknown",
                    author_name=item["commit"]["author"]["name"],
                    author_email=item["commit"]["author"]["email"],
                    committed_at=datetime.fromisoformat(
                        item["commit"]["author"]["date"].replace("Z", "+00:00")
                    ),
                    additions=commit_detail.get("stats", {}).get("additions", 0),  # type: ignore
                    deletions=commit_detail.get("stats", {}).get("deletions", 0),  # type: ignore
                    files_changed=len(commit_detail.get("files", [])),  # type: ignore
                    url=item["html_url"],
                )
            )

        return commits

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
    ) -> list[GitHubPullRequest]:
        """Get pull requests for a repository."""
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page},
        )

        prs = []
        for item in data:  # type: ignore
            merged_at = None
            if item.get("merged_at"):
                merged_at = datetime.fromisoformat(
                    item["merged_at"].replace("Z", "+00:00")
                )

            prs.append(
                GitHubPullRequest(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body"),
                    state=item["state"],
                    author_login=item["user"]["login"],
                    created_at=datetime.fromisoformat(
                        item["created_at"].replace("Z", "+00:00")
                    ),
                    updated_at=datetime.fromisoformat(
                        item["updated_at"].replace("Z", "+00:00")
                    ),
                    merged_at=merged_at,
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    changed_files=item.get("changed_files", 0),
                    url=item["html_url"],
                )
            )

        return prs

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
    ) -> list[GitHubIssue]:
        """Get issues for a repository (excludes PRs)."""
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": per_page},
        )

        issues = []
        for item in data:  # type: ignore
            # Skip pull requests (they appear in issues endpoint too)
            if "pull_request" in item:
                continue

            closed_at = None
            if item.get("closed_at"):
                closed_at = datetime.fromisoformat(
                    item["closed_at"].replace("Z", "+00:00")
                )

            issues.append(
                GitHubIssue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body"),
                    state=item["state"],
                    author_login=item["user"]["login"],
                    created_at=datetime.fromisoformat(
                        item["created_at"].replace("Z", "+00:00")
                    ),
                    updated_at=datetime.fromisoformat(
                        item["updated_at"].replace("Z", "+00:00")
                    ),
                    closed_at=closed_at,
                    labels=[label["name"] for label in item.get("labels", [])],
                    url=item["html_url"],
                )
            )

        return issues

    async def create_webhook(
        self,
        owner: str,
        repo: str,
        webhook_url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        """Create a webhook for a repository."""
        if events is None:
            events = ["push", "pull_request", "issues", "issue_comment", "pull_request_review"]

        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/hooks",
            json={
                "name": "web",
                "active": True,
                "events": events,
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0",
                },
            },
        )
        return data  # type: ignore

    async def delete_webhook(
        self, owner: str, repo: str, webhook_id: int
    ) -> None:
        """Delete a webhook."""
        await self.client.delete(f"/repos/{owner}/{repo}/hooks/{webhook_id}")
