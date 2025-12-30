"""Database models."""

from __future__ import annotations

from eldenops.db.models.attendance import (
    AttendanceLog,
    AttendancePattern,
    UserAttendanceStatus,
)
from eldenops.db.models.base import Base
from eldenops.db.models.discord import DiscordEvent, MonitoredChannel, VoiceSession
from eldenops.db.models.github import GitHubConnection, GitHubEvent
from eldenops.db.models.project import (
    GitHubIdentity,
    Project,
    ProjectGitHubLink,
    ProjectMember,
    TenantProjectConfig,
)
from eldenops.db.models.report import Report, ReportConfig
from eldenops.db.models.tenant import AIProviderConfig, Tenant, TenantMember
from eldenops.db.models.user import User

__all__ = [
    "Base",
    "Tenant",
    "TenantMember",
    "User",
    "AIProviderConfig",
    "MonitoredChannel",
    "DiscordEvent",
    "VoiceSession",
    "GitHubConnection",
    "GitHubEvent",
    "ReportConfig",
    "Report",
    "AttendanceLog",
    "AttendancePattern",
    "UserAttendanceStatus",
    "Project",
    "ProjectMember",
    "ProjectGitHubLink",
    "GitHubIdentity",
    "TenantProjectConfig",
]
