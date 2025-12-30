"""Report-related models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eldenops.config.constants import ReportType
from eldenops.db.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from eldenops.db.models.tenant import Tenant
    from eldenops.db.models.user import User


class ReportConfig(Base, UUIDMixin, TimestampMixin):
    """Saved report configurations."""

    __tablename__ = "report_configs"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Report definition
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    report_type: Mapped[str] = mapped_column(String(50), default=ReportType.CUSTOM)

    # Schedule (cron expression, null for on-demand)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100))
    is_scheduled_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Filters
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"date_range_days": 7, "channel_ids": [...], "user_ids": [...]}

    # Delivery configuration
    delivery_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"discord_channel_id": 123, "email": "exec@co.com", "webhook_url": "..."}

    # AI settings
    ai_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_prompt_override: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="report_configs")
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="config", cascade="all, delete-orphan"
    )

    @property
    def report_type_enum(self) -> ReportType:
        """Get report type as enum."""
        return ReportType(self.report_type)

    def __repr__(self) -> str:
        return f"<ReportConfig {self.name} ({self.report_type})>"


class Report(Base, UUIDMixin):
    """Generated reports."""

    __tablename__ = "reports"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("report_configs.id", ondelete="SET NULL"),
    )
    requested_by_user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Report metadata
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Date range covered
    date_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Content
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    # AI usage tracking
    ai_provider_used: Mapped[Optional[str]] = mapped_column(String(50))
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)

    # Timing
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    generation_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Delivery status
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Example: {"discord": {"success": true, "message_id": 123}, "email": {"success": false, "error": "..."}}

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="reports")
    config: Mapped["ReportConfig"] = relationship("ReportConfig", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report {self.title} generated={self.generated_at}>"
