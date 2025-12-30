"""Attendance tracking models."""

from __future__ import annotations

from datetime import datetime, time
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

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
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.tenant import Tenant
    from eldenops.db.models.user import User


class AttendanceEventType(str, Enum):
    """Types of attendance events."""

    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    BREAK_START = "break_start"
    BREAK_END = "break_end"


class BreakReasonCategory(str, Enum):
    """Categories for break reasons."""

    MEAL = "meal"
    PERSONAL = "personal"
    REST = "rest"
    MEETING = "meeting"
    EMERGENCY = "emergency"
    OTHER = "other"


class UserStatus(str, Enum):
    """Current user status."""

    ACTIVE = "active"
    ON_BREAK = "on_break"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AttendanceLog(Base, UUIDMixin, TimestampMixin):
    """Individual attendance events (check-in, check-out, breaks)."""

    __tablename__ = "attendance_logs"

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

    # Event classification
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Timing
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    expected_return_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    actual_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Context (AI-extracted)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    reason_category: Mapped[Optional[str]] = mapped_column(String(50))
    urgency: Mapped[str] = mapped_column(String(20), default="normal")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Source
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_message: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    parsed_by: Mapped[str] = mapped_column(String(50), default="regex")
    ai_model: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="attendance_logs")
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="attendance_logs"
    )

    @property
    def event_type_enum(self) -> AttendanceEventType:
        """Get event type as enum."""
        return AttendanceEventType(self.event_type)

    def __repr__(self) -> str:
        return f"<AttendanceLog {self.event_type} at {self.event_time}>"


class UserAttendanceStatus(Base, UUIDMixin, TimestampMixin):
    """Current attendance status for a user (cached/materialized view)."""

    __tablename__ = "user_attendance_status"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_attendance_status"),
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

    # Current status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    last_checkin_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_checkout_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_break_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    current_break_reason: Mapped[Optional[str]] = mapped_column(String(255))
    expected_return_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Today's summary (reset daily)
    today_checkin_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    today_total_break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    today_break_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User", back_populates="attendance_status")

    @property
    def status_enum(self) -> UserStatus:
        """Get status as enum."""
        return UserStatus(self.status)

    def __repr__(self) -> str:
        return f"<UserAttendanceStatus {self.user_id}: {self.status}>"


class AttendancePattern(Base, UUIDMixin, TimestampMixin):
    """Computed attendance patterns for analytics."""

    __tablename__ = "attendance_patterns"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "period_start", name="uq_attendance_pattern_period"
        ),
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

    # Computed patterns
    avg_checkin_time: Mapped[Optional[time]] = mapped_column(Time)
    avg_checkout_time: Mapped[Optional[time]] = mapped_column(Time)
    avg_work_hours_per_day: Mapped[Optional[float]] = mapped_column(Float)
    avg_breaks_per_day: Mapped[Optional[float]] = mapped_column(Float)
    avg_break_duration_minutes: Mapped[Optional[float]] = mapped_column(Float)

    # Day-of-week patterns
    weekly_patterns: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Break patterns
    common_break_times: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    common_break_reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Anomaly thresholds (auto-calculated)
    late_checkin_threshold: Mapped[Optional[time]] = mapped_column(Time)
    long_break_threshold_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Period
    period_start: Mapped[datetime] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime] = mapped_column(Date, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<AttendancePattern {self.user_id} ({self.period_start} - {self.period_end})>"
