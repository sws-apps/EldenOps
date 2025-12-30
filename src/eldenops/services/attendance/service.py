"""Attendance service for managing attendance events."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from eldenops.db.models.attendance import (
    AttendanceLog,
    UserAttendanceStatus,
    AttendanceEventType,
    UserStatus,
)
from eldenops.db.models.user import User
from eldenops.services.attendance.parser import (
    AttendanceParser,
    ParsedAttendance,
    ParsedEventType,
)
from eldenops.services.attendance.ai_parser import get_ai_parser
from eldenops.api.websocket import get_manager

logger = structlog.get_logger()


class AttendanceService:
    """Service for managing attendance events."""

    def __init__(self, db: AsyncSession, use_ai: bool = True):
        self.db = db
        self.regex_parser = AttendanceParser()
        self.use_ai = use_ai
        self._ai_parser = None

    @property
    def ai_parser(self):
        """Lazy load AI parser."""
        if self._ai_parser is None:
            self._ai_parser = get_ai_parser()
        return self._ai_parser

    async def process_message(
        self,
        tenant_id: str,
        discord_user_id: int,
        channel_id: int,
        message_id: int,
        message_content: str,
        message_time: datetime,
    ) -> Optional[AttendanceLog]:
        """Process a Discord message and create attendance log if applicable.

        Args:
            tenant_id: The tenant ID
            discord_user_id: Discord user ID
            channel_id: Discord channel ID
            message_id: Discord message ID
            message_content: The message text
            message_time: When the message was sent

        Returns:
            AttendanceLog if an event was detected, None otherwise
        """
        # Try AI parser first if enabled and available
        parsed = None
        if self.use_ai and self.ai_parser.is_available:
            parsed = await self.ai_parser.parse(message_content)
            if parsed:
                logger.debug(
                    "AI parsed message",
                    event_type=parsed.event_type.value,
                    confidence=parsed.confidence,
                )

        # Fallback to regex parser if AI didn't parse or isn't available
        if parsed is None:
            parsed = self.regex_parser.parse(message_content)
            logger.debug(
                "Regex parsed message",
                event_type=parsed.event_type.value,
                confidence=parsed.confidence,
            )

        if parsed.event_type == ParsedEventType.NONE:
            return None

        # Look up user
        user_result = await self.db.execute(
            select(User).where(User.discord_id == discord_user_id)
        )
        user = user_result.scalar_one_or_none()
        user_id = user.id if user else None

        # Create attendance log
        log = AttendanceLog(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=parsed.event_type.value,
            confidence=parsed.confidence,
            event_time=message_time,
            reason=parsed.reason,
            reason_category=parsed.reason_category.value if parsed.reason_category else None,
            urgency=parsed.urgency,
            expected_return_time=self._calculate_return_time(
                message_time, parsed.expected_duration_minutes
            ),
            channel_id=channel_id,
            message_id=message_id,
            raw_message=message_content,
            parsed_by=parsed.parsed_by,
        )
        self.db.add(log)

        # Update user status
        if user_id:
            await self._update_user_status(
                tenant_id=tenant_id,
                user_id=user_id,
                parsed=parsed,
                event_time=message_time,
            )

        await self.db.flush()

        logger.info(
            "Attendance event recorded",
            event_type=parsed.event_type.value,
            user_id=user_id,
            confidence=parsed.confidence,
            reason=parsed.reason,
        )

        return log

    async def _update_user_status(
        self,
        tenant_id: str,
        user_id: str,
        parsed: ParsedAttendance,
        event_time: datetime,
    ) -> None:
        """Update or create user attendance status."""
        # Get or create status record
        result = await self.db.execute(
            select(UserAttendanceStatus).where(
                and_(
                    UserAttendanceStatus.tenant_id == tenant_id,
                    UserAttendanceStatus.user_id == user_id,
                )
            )
        )
        status = result.scalar_one_or_none()

        if not status:
            status = UserAttendanceStatus(
                tenant_id=tenant_id,
                user_id=user_id,
                status=UserStatus.UNKNOWN.value,
            )
            self.db.add(status)

        # Update based on event type
        if parsed.event_type == ParsedEventType.CHECKIN:
            status.status = UserStatus.ACTIVE.value
            status.last_checkin_at = event_time
            status.today_checkin_at = event_time
            status.current_break_reason = None
            status.expected_return_at = None

        elif parsed.event_type == ParsedEventType.CHECKOUT:
            status.status = UserStatus.OFFLINE.value
            status.last_checkout_at = event_time
            status.current_break_reason = None
            status.expected_return_at = None

        elif parsed.event_type == ParsedEventType.BREAK_START:
            status.status = UserStatus.ON_BREAK.value
            status.last_break_start_at = event_time
            status.current_break_reason = parsed.reason
            status.today_break_count = (status.today_break_count or 0) + 1

            if parsed.expected_duration_minutes:
                status.expected_return_at = event_time + timedelta(
                    minutes=parsed.expected_duration_minutes
                )
            else:
                status.expected_return_at = None

        elif parsed.event_type == ParsedEventType.BREAK_END:
            # Calculate break duration
            if status.last_break_start_at:
                duration = event_time - status.last_break_start_at
                duration_minutes = int(duration.total_seconds() / 60)
                status.today_total_break_minutes = (
                    status.today_total_break_minutes or 0
                ) + duration_minutes

                # Update the last attendance log with actual duration
                await self._update_break_duration(
                    tenant_id, user_id, status.last_break_start_at, duration_minutes
                )

            status.status = UserStatus.ACTIVE.value
            status.current_break_reason = None
            status.expected_return_at = None

        status.updated_at = datetime.now(timezone.utc)

        # Broadcast the status update via WebSocket
        await self._broadcast_status_update(tenant_id, user_id, status, parsed)

    async def _broadcast_status_update(
        self,
        tenant_id: str,
        user_id: str,
        status: UserAttendanceStatus,
        parsed: ParsedAttendance,
    ) -> None:
        """Broadcast attendance status update via WebSocket."""
        try:
            # Get user info for the broadcast
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                manager = get_manager()
                connection_count = manager.get_connection_count(str(tenant_id))
                logger.info(
                    "Broadcasting attendance update",
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                    status=status.status,
                    connections=connection_count,
                )
                await manager.broadcast_attendance_update(
                    tenant_id,
                    {
                        "user_id": str(user_id),
                        "discord_id": user.discord_id,
                        "discord_username": user.discord_username,
                        "status": status.status,
                        "event_type": parsed.event_type.value,
                        "reason": parsed.reason,
                        "expected_return_at": status.expected_return_at.isoformat() if status.expected_return_at else None,
                        "last_checkin_at": status.last_checkin_at.isoformat() if status.last_checkin_at else None,
                        "last_checkout_at": status.last_checkout_at.isoformat() if status.last_checkout_at else None,
                    }
                )
                logger.debug("Broadcast attendance update", user_id=user_id, status=status.status)
        except Exception as e:
            # Don't fail the whole operation if broadcast fails
            logger.warning("Failed to broadcast attendance update", error=str(e))

    async def _update_break_duration(
        self,
        tenant_id: str,
        user_id: str,
        break_start_time: datetime,
        duration_minutes: int,
    ) -> None:
        """Update the break start log with actual duration."""
        result = await self.db.execute(
            select(AttendanceLog)
            .where(
                and_(
                    AttendanceLog.tenant_id == tenant_id,
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.event_type == AttendanceEventType.BREAK_START.value,
                    AttendanceLog.event_time >= break_start_time - timedelta(minutes=1),
                    AttendanceLog.event_time <= break_start_time + timedelta(minutes=1),
                )
            )
            .order_by(AttendanceLog.event_time.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()

        if log:
            log.actual_duration_minutes = duration_minutes

    def _calculate_return_time(
        self, event_time: datetime, duration_minutes: Optional[int]
    ) -> Optional[datetime]:
        """Calculate expected return time."""
        if duration_minutes:
            return event_time + timedelta(minutes=duration_minutes)
        return None

    async def get_team_status(self, tenant_id: str) -> list[dict]:
        """Get current status for all team members.

        Returns:
            List of user status dictionaries
        """
        result = await self.db.execute(
            select(UserAttendanceStatus, User)
            .join(User, UserAttendanceStatus.user_id == User.id)
            .where(UserAttendanceStatus.tenant_id == tenant_id)
            .order_by(User.discord_username)
        )

        team_status = []
        for status, user in result:
            team_status.append({
                "user_id": user.id,
                "discord_id": user.discord_id,
                "discord_username": user.discord_username,
                "status": status.status,
                "last_checkin_at": status.last_checkin_at,
                "last_checkout_at": status.last_checkout_at,
                "last_break_start_at": status.last_break_start_at,
                "current_break_reason": status.current_break_reason,
                "expected_return_at": status.expected_return_at,
                "today_stats": {
                    "checkin_at": status.today_checkin_at,
                    "break_count": status.today_break_count or 0,
                    "total_break_minutes": status.today_total_break_minutes or 0,
                },
            })

        return team_status

    async def get_user_history(
        self,
        tenant_id: str,
        user_id: str,
        days: int = 7,
    ) -> list[AttendanceLog]:
        """Get attendance history for a user.

        Args:
            tenant_id: The tenant ID
            user_id: The user ID
            days: Number of days to look back

        Returns:
            List of AttendanceLog entries
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(AttendanceLog)
            .where(
                and_(
                    AttendanceLog.tenant_id == tenant_id,
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.event_time >= since,
                )
            )
            .order_by(AttendanceLog.event_time.desc())
        )

        return list(result.scalars().all())

    async def reset_daily_stats(self, tenant_id: str) -> None:
        """Reset daily statistics for all users.

        Should be called at the start of each day.
        """
        result = await self.db.execute(
            select(UserAttendanceStatus).where(
                UserAttendanceStatus.tenant_id == tenant_id
            )
        )

        for status in result.scalars():
            status.today_checkin_at = None
            status.today_total_break_minutes = 0
            status.today_break_count = 0
            status.updated_at = datetime.now(timezone.utc)

        logger.info("Daily attendance stats reset", tenant_id=tenant_id)
