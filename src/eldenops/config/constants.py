"""Application constants."""

from __future__ import annotations

from enum import Enum


class AIProvider(str, Enum):
    """Supported AI providers."""

    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


class TenantRole(str, Enum):
    """User roles within a tenant."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ChannelType(str, Enum):
    """Discord channel types we track."""

    TEXT = "text"
    VOICE = "voice"
    ANNOUNCEMENT = "announcement"
    FORUM = "forum"
    THREAD = "thread"


class DiscordEventType(str, Enum):
    """Discord event types we track."""

    MESSAGE = "message"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_DELETE = "message_delete"
    REACTION_ADD = "reaction_add"
    VOICE_JOIN = "voice_join"
    VOICE_LEAVE = "voice_leave"
    THREAD_CREATE = "thread_create"


class GitHubEventType(str, Enum):
    """GitHub event types we track."""

    COMMIT = "commit"
    PR_OPENED = "pr_opened"
    PR_CLOSED = "pr_closed"
    PR_MERGED = "pr_merged"
    PR_REVIEW = "pr_review"
    PR_COMMENT = "pr_comment"
    ISSUE_OPENED = "issue_opened"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_COMMENT = "issue_comment"


class ReportType(str, Enum):
    """Report types."""

    DAILY_SUMMARY = "daily_summary"
    WEEKLY_DIGEST = "weekly_digest"
    PROJECT_STATUS = "project_status"
    TEAM_ACTIVITY = "team_activity"
    CUSTOM = "custom"


# Discord permission flags for admin commands
ADMIN_PERMISSIONS = ["administrator", "manage_guild"]

# Rate limits
AI_REQUESTS_PER_MINUTE = 50
AI_TOKENS_PER_MINUTE = 100000

# Data retention (days)
DEFAULT_DATA_RETENTION_DAYS = 90

# Report generation
MAX_MESSAGES_PER_ANALYSIS = 500
MAX_COMMITS_PER_SUMMARY = 100
