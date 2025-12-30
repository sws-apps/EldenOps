"""User model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.attendance import AttendanceLog, UserAttendanceStatus
    from eldenops.db.models.tenant import TenantMember
    from eldenops.db.models.project import ProjectMember, GitHubIdentity


class User(Base, UUIDMixin, TimestampMixin):
    """User linked to Discord and optionally GitHub."""

    __tablename__ = "users"

    # Discord info (primary identity)
    discord_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    discord_username: Mapped[Optional[str]] = mapped_column(String(255))
    discord_avatar_url: Mapped[Optional[str]] = mapped_column(Text)

    # Contact info (optional)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # GitHub integration (optional)
    github_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(255))
    github_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Timezone for availability analysis
    timezone: Mapped[Optional[str]] = mapped_column(String(50))

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant_memberships: Mapped[list["TenantMember"]] = relationship(
        "TenantMember", back_populates="user", cascade="all, delete-orphan"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="user"
    )
    attendance_status: Mapped[Optional["UserAttendanceStatus"]] = relationship(
        "UserAttendanceStatus", back_populates="user", uselist=False
    )
    project_assignments: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="user", cascade="all, delete-orphan"
    )
    github_identities: Mapped[list["GitHubIdentity"]] = relationship(
        "GitHubIdentity", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.discord_username} ({self.discord_id})>"
