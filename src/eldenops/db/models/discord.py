"""Discord-related models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.config.constants import ChannelType, DiscordEventType
from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.tenant import Tenant
    from eldenops.db.models.user import User


class MonitoredChannel(Base, UUIDMixin, TimestampMixin):
    """Discord channels being monitored for a tenant."""

    __tablename__ = "monitored_channels"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(255))
    channel_type: Mapped[str] = mapped_column(String(50), default=ChannelType.TEXT)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # For threads

    # Configuration
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tracking_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="monitored_channels"
    )

    @property
    def channel_type_enum(self) -> ChannelType:
        """Get channel type as enum."""
        return ChannelType(self.channel_type)

    def __repr__(self) -> str:
        return f"<MonitoredChannel #{self.channel_name} ({self.channel_id})>"


class DiscordEvent(Base, UUIDMixin):
    """Discord activity events (metadata only, not message content)."""

    __tablename__ = "discord_events"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Metadata (no message content for privacy)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    has_links: Mapped[bool] = mapped_column(Boolean, default=False)
    has_mentions: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    thread_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Additional metadata
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="discord_events")

    @property
    def event_type_enum(self) -> DiscordEventType:
        """Get event type as enum."""
        return DiscordEventType(self.event_type)

    def __repr__(self) -> str:
        return f"<DiscordEvent {self.event_type} at {self.created_at}>"


class VoiceSession(Base, UUIDMixin):
    """Voice channel session tracking."""

    __tablename__ = "voice_sessions"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Session timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # State tracking
    muted_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    deafened_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<VoiceSession channel={self.channel_id} started={self.started_at}>"
