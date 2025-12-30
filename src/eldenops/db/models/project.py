"""Project and Team Member mapping models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.tenant import Tenant
    from eldenops.db.models.user import User


class ProjectStatus(str, Enum):
    """Project status options."""
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MemberRole(str, Enum):
    """Team member roles in a project."""
    LEAD = "lead"
    DEVELOPER = "developer"
    DESIGNER = "designer"
    QA = "qa"
    STAKEHOLDER = "stakeholder"
    OBSERVER = "observer"


class Project(Base, UUIDMixin, TimestampMixin):
    """Project entity linking Discord threads and GitHub repos."""

    __tablename__ = "projects"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default=ProjectStatus.ACTIVE)

    # Discord linking
    discord_thread_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    discord_thread_name: Mapped[Optional[str]] = mapped_column(String(255))
    discord_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Timeline
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    target_launch_date: Mapped[Optional[datetime]] = mapped_column(Date)
    actual_launch_date: Mapped[Optional[datetime]] = mapped_column(Date)

    # Goals and objectives (flexible JSON structure)
    objectives: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"goals": ["Launch MVP", "Get 100 users"], "success_criteria": [...]}

    # KPIs configuration (flexible per project)
    kpi_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"velocity_target": 10, "pr_review_time_hours": 24, ...}

    # Launch checklist (flexible)
    launch_checklist: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"items": [{"name": "Testing", "completed": false}, ...]}

    # AI-generated insights cache
    last_ai_analysis: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ai_insights: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="projects")
    members: Mapped[List["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )
    github_links: Mapped[List["ProjectGitHubLink"]] = relationship(
        "ProjectGitHubLink", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.status})>"


class ProjectMember(Base, UUIDMixin, TimestampMixin):
    """Assignment of a team member to a project."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role in this project
    role: Mapped[str] = mapped_column(String(50), default=MemberRole.DEVELOPER)

    # Assignment details
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    assigned_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    # Responsibilities (flexible)
    responsibilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"areas": ["backend", "api"], "tasks": ["Implement auth"]}

    # Activity tracking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="project_assignments")

    def __repr__(self) -> str:
        return f"<ProjectMember {self.user_id} on {self.project_id} ({self.role})>"


class ProjectGitHubLink(Base, UUIDMixin, TimestampMixin):
    """Link between a project and GitHub repository."""

    __tablename__ = "project_github_links"
    __table_args__ = (
        UniqueConstraint("project_id", "github_connection_id", name="uq_project_github"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_connection_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("github_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional: specific branch to track
    branch_filter: Mapped[Optional[str]] = mapped_column(String(255))

    # Is this the primary repo for the project?
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="github_links")
    github_connection: Mapped["GitHubConnection"] = relationship("GitHubConnection")

    def __repr__(self) -> str:
        return f"<ProjectGitHubLink {self.project_id} -> {self.github_connection_id}>"


class GitHubIdentity(Base, UUIDMixin, TimestampMixin):
    """Map GitHub committer identities to team members.

    Git commits can have different author emails/names than GitHub username.
    This table maps those identities to the actual user.
    """

    __tablename__ = "github_identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "committer_email", name="uq_github_identity_email"),
    )

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Git committer identity
    committer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    committer_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Auto-detected or manually added
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User", back_populates="github_identities")

    def __repr__(self) -> str:
        return f"<GitHubIdentity {self.committer_email} -> {self.user_id}>"


class TenantProjectConfig(Base, UUIDMixin, TimestampMixin):
    """Per-tenant configuration for project tracking.

    Allows each organization to customize how projects are detected,
    named, and tracked based on their Discord structure.
    """

    __tablename__ = "tenant_project_configs"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Task delegation channel configuration
    task_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    task_channel_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Thread naming convention parsing
    # Example patterns:
    # "{member} ({project})" -> "Jeo (CUA-BOT)"
    # "{project} - {member}" -> "CUA-BOT - Jeo"
    # "{project}" -> "CUA-BOT"
    thread_name_pattern: Mapped[str] = mapped_column(
        String(255), default="{member} ({project})"
    )

    # Auto-create projects from threads
    auto_create_projects: Mapped[bool] = mapped_column(Boolean, default=True)

    # Report configuration
    report_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {
    #   "daily": {"enabled": true, "time": "09:00"},
    #   "weekly": {"enabled": true, "day": "monday"},
    #   "monthly": {"enabled": true, "day": 1}
    # }

    # KPI defaults for new projects
    default_kpis: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # AI analysis configuration
    ai_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {
    #   "analyze_frequency": "daily",
    #   "suggestion_types": ["blockers", "next_steps", "risks"],
    #   "context_window_days": 30
    # }

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="project_config")

    def __repr__(self) -> str:
        return f"<TenantProjectConfig for {self.tenant_id}>"


# Import at the end to avoid circular imports
from eldenops.db.models.github import GitHubConnection
