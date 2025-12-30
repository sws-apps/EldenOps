"""Attendance tracking API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
import structlog

from eldenops.api.deps import CurrentUser, DBSession, TenantID
from eldenops.services.attendance import AttendanceService

logger = structlog.get_logger()
router = APIRouter()


class UserStatusResponse(BaseModel):
    """User attendance status."""

    user_id: str
    discord_id: int
    discord_username: Optional[str]
    status: str
    last_checkin_at: Optional[datetime]
    last_checkout_at: Optional[datetime]
    last_break_start_at: Optional[datetime]
    current_break_reason: Optional[str]
    expected_return_at: Optional[datetime]
    today_stats: dict[str, Any]


class TeamStatusResponse(BaseModel):
    """Team attendance status response."""

    team_status: list[UserStatusResponse]
    summary: dict[str, int]


class AttendanceLogResponse(BaseModel):
    """Attendance log entry."""

    id: str
    event_type: str
    event_time: datetime
    reason: Optional[str]
    reason_category: Optional[str]
    actual_duration_minutes: Optional[int]
    confidence: Optional[float]


@router.get("/status")
async def get_team_status(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
) -> TeamStatusResponse:
    """Get current attendance status for all team members.

    Returns who is active, on break, or offline.
    """
    logger.info("Getting team attendance status", tenant_id=tenant_id)

    service = AttendanceService(db)
    team_status = await service.get_team_status(tenant_id)

    # Calculate summary
    summary = {
        "active": 0,
        "on_break": 0,
        "offline": 0,
        "unknown": 0,
    }

    for status in team_status:
        status_type = status.get("status", "unknown")
        if status_type in summary:
            summary[status_type] += 1
        else:
            summary["unknown"] += 1

    return TeamStatusResponse(
        team_status=[UserStatusResponse(**s) for s in team_status],
        summary=summary,
    )


@router.get("/users/{user_id}/history")
async def get_user_history(
    user_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=90),
) -> list[AttendanceLogResponse]:
    """Get attendance history for a specific user.

    Returns check-ins, check-outs, and breaks for the specified period.
    """
    logger.info(
        "Getting user attendance history",
        tenant_id=tenant_id,
        user_id=user_id,
        days=days,
    )

    service = AttendanceService(db)
    logs = await service.get_user_history(tenant_id, user_id, days)

    return [
        AttendanceLogResponse(
            id=log.id,
            event_type=log.event_type,
            event_time=log.event_time,
            reason=log.reason,
            reason_category=log.reason_category,
            actual_duration_minutes=log.actual_duration_minutes,
            confidence=log.confidence,
        )
        for log in logs
    ]


@router.get("/users/{user_id}/patterns")
async def get_user_patterns(
    user_id: str,
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=30, ge=7, le=90),
) -> dict[str, Any]:
    """Get attendance patterns for a specific user.

    Returns computed patterns like average check-in time, break frequency, etc.
    """
    logger.info(
        "Getting user attendance patterns",
        tenant_id=tenant_id,
        user_id=user_id,
        days=days,
    )

    service = AttendanceService(db)
    logs = await service.get_user_history(tenant_id, user_id, days)

    if not logs:
        return {
            "user_id": user_id,
            "period_days": days,
            "patterns": None,
            "message": "Not enough data to compute patterns",
        }

    # Compute patterns from logs
    checkins = [log for log in logs if log.event_type == "checkin"]
    checkouts = [log for log in logs if log.event_type == "checkout"]
    breaks = [log for log in logs if log.event_type == "break_start"]

    patterns = {
        "total_checkins": len(checkins),
        "total_checkouts": len(checkouts),
        "total_breaks": len(breaks),
    }

    # Calculate average check-in time
    if checkins:
        checkin_times = [log.event_time.hour * 60 + log.event_time.minute for log in checkins]
        avg_checkin_minutes = sum(checkin_times) / len(checkin_times)
        patterns["avg_checkin_time"] = f"{int(avg_checkin_minutes // 60):02d}:{int(avg_checkin_minutes % 60):02d}"

    # Calculate average checkout time
    if checkouts:
        checkout_times = [log.event_time.hour * 60 + log.event_time.minute for log in checkouts]
        avg_checkout_minutes = sum(checkout_times) / len(checkout_times)
        patterns["avg_checkout_time"] = f"{int(avg_checkout_minutes // 60):02d}:{int(avg_checkout_minutes % 60):02d}"

    # Calculate break statistics
    if breaks:
        patterns["avg_breaks_per_day"] = round(len(breaks) / days, 1)

        # Break reasons distribution
        reason_counts: dict[str, int] = {}
        for log in breaks:
            category = log.reason_category or "other"
            reason_counts[category] = reason_counts.get(category, 0) + 1

        patterns["break_reason_distribution"] = {
            k: round(v / len(breaks) * 100, 1)
            for k, v in reason_counts.items()
        }

        # Average break duration
        durations = [log.actual_duration_minutes for log in breaks if log.actual_duration_minutes]
        if durations:
            patterns["avg_break_duration_minutes"] = round(sum(durations) / len(durations), 1)

    return {
        "user_id": user_id,
        "period_days": days,
        "patterns": patterns,
    }


@router.get("/summary")
async def get_attendance_summary(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    """Get attendance summary for the team.

    Returns aggregate statistics for the specified period.
    """
    from sqlalchemy import select, func
    from eldenops.db.models.attendance import AttendanceLog

    logger.info(
        "Getting attendance summary",
        tenant_id=tenant_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get event counts by type
    result = await db.execute(
        select(
            AttendanceLog.event_type,
            func.count(AttendanceLog.id).label("count"),
        )
        .where(
            AttendanceLog.tenant_id == tenant_id,
            AttendanceLog.event_time >= since,
        )
        .group_by(AttendanceLog.event_type)
    )

    event_counts = {row.event_type: row.count for row in result}

    # Get unique users
    unique_users_result = await db.execute(
        select(func.count(func.distinct(AttendanceLog.user_id)))
        .where(
            AttendanceLog.tenant_id == tenant_id,
            AttendanceLog.event_time >= since,
        )
    )
    unique_users = unique_users_result.scalar() or 0

    return {
        "period_days": days,
        "event_counts": event_counts,
        "unique_users": unique_users,
        "total_events": sum(event_counts.values()),
    }


@router.get("/insights")
async def get_attendance_insights(
    tenant_id: TenantID,
    current_user: CurrentUser,
    db: DBSession,
    days: int = Query(default=30, ge=7, le=90),
) -> dict[str, Any]:
    """Get behavioral insights from attendance data.

    Returns patterns like typical check-in times, break patterns, etc.
    """
    from sqlalchemy import select, func, extract
    from eldenops.db.models.attendance import AttendanceLog
    from eldenops.db.models.user import User

    logger.info(
        "Getting attendance insights",
        tenant_id=tenant_id,
        days=days,
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Get all logs for analysis
    result = await db.execute(
        select(AttendanceLog, User.discord_username)
        .join(User, AttendanceLog.user_id == User.id)
        .where(
            AttendanceLog.tenant_id == tenant_id,
            AttendanceLog.event_time >= since,
        )
        .order_by(AttendanceLog.event_time)
    )
    rows = result.all()

    if not rows:
        return {
            "period_days": days,
            "has_data": False,
            "message": "No attendance data for this period",
        }

    # Analyze check-in times (hour distribution)
    checkin_hours: dict[int, int] = {}
    checkout_hours: dict[int, int] = {}
    break_hours: dict[int, int] = {}

    # Break reasons analysis
    break_reasons: dict[str, int] = {}
    long_breaks: list[dict] = []  # Breaks over 30 minutes

    # Per-user patterns
    user_patterns: dict[str, dict] = {}

    for log, username in rows:
        hour = log.event_time.hour
        user_id = str(log.user_id)

        # Initialize user pattern tracking
        if user_id not in user_patterns:
            user_patterns[user_id] = {
                "username": username,
                "checkin_times": [],
                "checkout_times": [],
                "break_count": 0,
                "total_break_minutes": 0,
            }

        if log.event_type == "checkin":
            checkin_hours[hour] = checkin_hours.get(hour, 0) + 1
            user_patterns[user_id]["checkin_times"].append(hour)

        elif log.event_type == "checkout":
            checkout_hours[hour] = checkout_hours.get(hour, 0) + 1
            user_patterns[user_id]["checkout_times"].append(hour)

        elif log.event_type == "break_start":
            break_hours[hour] = break_hours.get(hour, 0) + 1
            user_patterns[user_id]["break_count"] += 1

            # Track break reasons
            reason = log.reason_category or log.reason or "unspecified"
            break_reasons[reason] = break_reasons.get(reason, 0) + 1

            # Track long breaks
            if log.actual_duration_minutes and log.actual_duration_minutes > 30:
                long_breaks.append({
                    "username": username,
                    "duration_minutes": log.actual_duration_minutes,
                    "reason": log.reason or "No reason given",
                    "time": log.event_time.isoformat(),
                })
                user_patterns[user_id]["total_break_minutes"] += log.actual_duration_minutes

    # Calculate peak hours
    def get_peak_hours(hour_dist: dict[int, int], top_n: int = 3) -> list[dict]:
        sorted_hours = sorted(hour_dist.items(), key=lambda x: x[1], reverse=True)
        return [
            {"hour": h, "count": c, "time": f"{h:02d}:00"}
            for h, c in sorted_hours[:top_n]
        ]

    # Calculate average times
    def calc_avg_hour(hour_dist: dict[int, int]) -> Optional[str]:
        if not hour_dist:
            return None
        total_weight = sum(h * c for h, c in hour_dist.items())
        total_count = sum(hour_dist.values())
        avg_hour = total_weight / total_count
        hours = int(avg_hour)
        minutes = int((avg_hour - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    # Sort break reasons by frequency
    sorted_reasons = sorted(break_reasons.items(), key=lambda x: x[1], reverse=True)

    # Identify users with most breaks
    users_by_breaks = sorted(
        user_patterns.items(),
        key=lambda x: x[1]["break_count"],
        reverse=True
    )[:5]

    # Identify early birds (earliest avg check-in)
    early_birds = []
    for user_id, data in user_patterns.items():
        if data["checkin_times"]:
            avg_checkin = sum(data["checkin_times"]) / len(data["checkin_times"])
            early_birds.append({
                "username": data["username"],
                "avg_checkin_hour": avg_checkin,
                "avg_checkin_time": f"{int(avg_checkin):02d}:{int((avg_checkin % 1) * 60):02d}",
            })
    early_birds.sort(key=lambda x: x["avg_checkin_hour"])

    # Identify night owls (latest avg checkout)
    night_owls = []
    for user_id, data in user_patterns.items():
        if data["checkout_times"]:
            avg_checkout = sum(data["checkout_times"]) / len(data["checkout_times"])
            night_owls.append({
                "username": data["username"],
                "avg_checkout_hour": avg_checkout,
                "avg_checkout_time": f"{int(avg_checkout):02d}:{int((avg_checkout % 1) * 60):02d}",
            })
    night_owls.sort(key=lambda x: x["avg_checkout_hour"], reverse=True)

    return {
        "period_days": days,
        "has_data": True,
        "checkin_patterns": {
            "peak_hours": get_peak_hours(checkin_hours),
            "average_time": calc_avg_hour(checkin_hours),
            "hour_distribution": {f"{h:02d}:00": c for h, c in sorted(checkin_hours.items())},
        },
        "checkout_patterns": {
            "peak_hours": get_peak_hours(checkout_hours),
            "average_time": calc_avg_hour(checkout_hours),
            "hour_distribution": {f"{h:02d}:00": c for h, c in sorted(checkout_hours.items())},
        },
        "break_patterns": {
            "peak_hours": get_peak_hours(break_hours),
            "average_time": calc_avg_hour(break_hours),
            "hour_distribution": {f"{h:02d}:00": c for h, c in sorted(break_hours.items())},
            "reasons": [{"reason": r, "count": c} for r, c in sorted_reasons[:10]],
            "long_breaks": sorted(long_breaks, key=lambda x: x["duration_minutes"], reverse=True)[:10],
        },
        "team_insights": {
            "early_birds": early_birds[:5],
            "night_owls": night_owls[:5],
            "most_breaks": [
                {"username": data["username"], "break_count": data["break_count"]}
                for _, data in users_by_breaks
            ],
        },
    }
