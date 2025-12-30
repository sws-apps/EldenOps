"""GitHub-related models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.config.constants import GitHubEventType
from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.tenant import Tenant
    from eldenops.db.models.user import User


class GitHubConnection(Base, UUIDMixin, TimestampMixin):
    """Connected GitHub repositories for a tenant."""

    __tablename__ = "github_connections"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connected_by_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Repository info
    org_name: Mapped[Optional[str]] = mapped_column(String(255))
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_full_name: Mapped[str] = mapped_column(
        String(511), nullable=False, index=True
    )  # org/repo
    repo_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Webhook configuration
    webhook_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Sync configuration
    sync_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="github_connections"
    )

    def __repr__(self) -> str:
        return f"<GitHubConnection {self.repo_full_name}>"


class GitHubEvent(Base, UUIDMixin):
    """GitHub activity events."""

    __tablename__ = "github_events"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("github_connections.id", ondelete="SET NULL"),
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    # GitHub user info (for users not in our system)
    github_user_login: Mapped[Optional[str]] = mapped_column(String(255))
    github_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    repo_full_name: Mapped[str] = mapped_column(String(511), nullable=False, index=True)

    # Reference identifiers
    ref_id: Mapped[Optional[str]] = mapped_column(String(255))  # SHA, PR number, etc.
    ref_url: Mapped[Optional[str]] = mapped_column(Text)

    # Content summary
    title: Mapped[Optional[str]] = mapped_column(Text)
    body_preview: Mapped[Optional[str]] = mapped_column(Text)  # First 500 chars

    # Metrics
    additions: Mapped[Optional[int]] = mapped_column(Integer)
    deletions: Mapped[Optional[int]] = mapped_column(Integer)
    files_changed: Mapped[Optional[int]] = mapped_column(Integer)

    # Additional metadata
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="github_events")

    @property
    def event_type_enum(self) -> GitHubEventType:
        """Get event type as enum."""
        return GitHubEventType(self.event_type)

    def __repr__(self) -> str:
        return f"<GitHubEvent {self.event_type} {self.ref_id} at {self.created_at}>"
