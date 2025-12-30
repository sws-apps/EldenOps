"""Tenant and multi-tenancy models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.config.constants import AIProvider, TenantRole
from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.attendance import AttendanceLog
    from eldenops.db.models.discord import DiscordEvent, MonitoredChannel
    from eldenops.db.models.github import GitHubConnection, GitHubEvent
    from eldenops.db.models.report import Report, ReportConfig
    from eldenops.db.models.user import User
    from eldenops.db.models.project import Project, TenantProjectConfig


class Tenant(Base, UUIDMixin, TimestampMixin):
    """Represents a Discord server (guild) as a tenant."""

    __tablename__ = "tenants"

    # Discord guild info
    discord_guild_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    guild_name: Mapped[Optional[str]] = mapped_column(String(255))
    guild_icon_url: Mapped[Optional[str]] = mapped_column(Text)

    # Owner (Discord user ID who set up the bot)
    owner_discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Settings
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # GitHub integration
    github_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    members: Mapped[list["TenantMember"]] = relationship(
        "TenantMember", back_populates="tenant", cascade="all, delete-orphan"
    )
    monitored_channels: Mapped[list["MonitoredChannel"]] = relationship(
        "MonitoredChannel", back_populates="tenant", cascade="all, delete-orphan"
    )
    github_connections: Mapped[list["GitHubConnection"]] = relationship(
        "GitHubConnection", back_populates="tenant", cascade="all, delete-orphan"
    )
    ai_provider_configs: Mapped[list["AIProviderConfig"]] = relationship(
        "AIProviderConfig", back_populates="tenant", cascade="all, delete-orphan"
    )
    discord_events: Mapped[list["DiscordEvent"]] = relationship(
        "DiscordEvent", back_populates="tenant", cascade="all, delete-orphan"
    )
    github_events: Mapped[list["GitHubEvent"]] = relationship(
        "GitHubEvent", back_populates="tenant", cascade="all, delete-orphan"
    )
    report_configs: Mapped[list["ReportConfig"]] = relationship(
        "ReportConfig", back_populates="tenant", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="tenant", cascade="all, delete-orphan"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="tenant", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="tenant", cascade="all, delete-orphan"
    )
    project_config: Mapped[Optional["TenantProjectConfig"]] = relationship(
        "TenantProjectConfig", back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.guild_name} ({self.discord_guild_id})>"


class TenantMember(Base, UUIDMixin, TimestampMixin):
    """Links users to tenants with roles."""

    __tablename__ = "tenant_members"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50), default=TenantRole.MEMBER, nullable=False
    )
    # Cache of Discord role IDs for permission checks
    discord_roles: Mapped[list[int]] = mapped_column(JSONB, default=list)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="tenant_memberships")

    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in (TenantRole.OWNER, TenantRole.ADMIN)

    def __repr__(self) -> str:
        return f"<TenantMember user={self.user_id} tenant={self.tenant_id} role={self.role}>"


class AIProviderConfig(Base, UUIDMixin, TimestampMixin):
    """Per-tenant AI provider configuration."""

    __tablename__ = "ai_provider_configs"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # AIProvider enum
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    model_preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Usage tracking
    usage_limits: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="ai_provider_configs"
    )

    @property
    def provider_enum(self) -> AIProvider:
        """Get provider as enum."""
        return AIProvider(self.provider)

    def __repr__(self) -> str:
        return f"<AIProviderConfig {self.provider} for tenant={self.tenant_id}>"
