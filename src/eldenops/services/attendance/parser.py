"""Attendance message parser.

Parses Discord messages to detect attendance events:
- Check-in: "✅ Available", "Available", etc.
- Check-out: "👋 Signing Out", "Signing Out", etc.
- Break start: "BRB", "BRB - reason", etc.
- Break end: "back", "I'm back", etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class ParsedEventType(str, Enum):
    """Types of parsed attendance events."""

    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    BREAK_START = "break_start"
    BREAK_END = "break_end"
    NONE = "none"  # Not an attendance message


class BreakReasonCategory(str, Enum):
    """Categories for break reasons."""

    MEAL = "meal"
    PERSONAL = "personal"
    REST = "rest"
    MEETING = "meeting"
    EMERGENCY = "emergency"
    OTHER = "other"


@dataclass
class ParsedAttendance:
    """Result of parsing an attendance message."""

    event_type: ParsedEventType
    confidence: float
    reason: Optional[str] = None
    reason_category: Optional[BreakReasonCategory] = None
    expected_duration_minutes: Optional[int] = None
    urgency: str = "normal"
    notes: Optional[str] = None
    parsed_by: str = "regex"


class AttendanceParser:
    """Parses Discord messages to detect attendance events."""

    # EldenDev team-specific patterns
    CHECKIN_PATTERNS = [
        # "✅ Available" or just "Available"
        re.compile(r"^[✅☑️✓]?\s*available\s*$", re.IGNORECASE),
        # Generic check-in patterns
        re.compile(r"^(good\s*morning|gm|online|in)\s*[!.]?\s*$", re.IGNORECASE),
        re.compile(r"^(hello|hi|hey)\s*(everyone|team|all)?[!.]?\s*$", re.IGNORECASE),
    ]

    CHECKOUT_PATTERNS = [
        # "👋 Signing Out" or "🌙 Signing Out"
        re.compile(r"^[👋🖐️✋🌙]?\s*signing\s*out\s*$", re.IGNORECASE),
        # Generic check-out patterns
        re.compile(r"^(logging\s*off|log\s*off|out|eod|end\s*of\s*day)\s*[!.]?\s*$", re.IGNORECASE),
        re.compile(r"^(good\s*night|gn|bye|leaving|done)\s*[!.]?\s*$", re.IGNORECASE),
    ]

    # BRB with optional reason: "BRB" or "BRB - going to lunch"
    BREAK_START_PATTERN = re.compile(
        r"^brb(?:\s*[-–—:]\s*(?P<reason>.+))?\s*$", re.IGNORECASE
    )

    BREAK_START_ALT_PATTERNS = [
        re.compile(r"^(break|afk|lunch|stepping\s*out)\s*$", re.IGNORECASE),
        re.compile(r"^(taking\s*(?:a\s*)?break)\s*[-–—:]?\s*(?P<reason>.*)$", re.IGNORECASE),
    ]

    BREAK_END_PATTERNS = [
        re.compile(r"^back\s*[!.]?\s*$", re.IGNORECASE),
        re.compile(r"^(i'?m\s*back|here|returned|resuming)\s*[!.]?\s*$", re.IGNORECASE),
    ]

    # Keywords for categorizing break reasons
    MEAL_KEYWORDS = ["lunch", "dinner", "breakfast", "eat", "food", "meal", "snack", "coffee"]
    PERSONAL_KEYWORDS = ["errand", "appointment", "doctor", "dentist", "pickup", "drop", "bank", "store", "daughter", "son", "kid", "child", "family"]
    REST_KEYWORDS = ["rest", "nap", "tired", "break", "stretch", "walk"]
    MEETING_KEYWORDS = ["meeting", "call", "standup", "sync", "interview"]
    EMERGENCY_KEYWORDS = ["emergency", "urgent", "asap", "important"]

    # Duration extraction patterns
    DURATION_PATTERNS = [
        re.compile(r"(\d+)\s*(?:min(?:ute)?s?|m)\b", re.IGNORECASE),
        re.compile(r"(\d+)\s*(?:hour?s?|hr?s?)\b", re.IGNORECASE),
        re.compile(r"(?:in|back\s*in)\s*(\d+)", re.IGNORECASE),
    ]

    def parse(self, message: str) -> ParsedAttendance:
        """Parse a message and return the attendance event if detected.

        Args:
            message: The Discord message content

        Returns:
            ParsedAttendance with event details
        """
        message = message.strip()

        if not message:
            return ParsedAttendance(
                event_type=ParsedEventType.NONE,
                confidence=1.0,
            )

        # Try each pattern type in order
        result = self._try_checkin(message)
        if result:
            return result

        result = self._try_checkout(message)
        if result:
            return result

        result = self._try_break_start(message)
        if result:
            return result

        result = self._try_break_end(message)
        if result:
            return result

        # No match
        return ParsedAttendance(
            event_type=ParsedEventType.NONE,
            confidence=1.0,
        )

    def _try_checkin(self, message: str) -> Optional[ParsedAttendance]:
        """Try to parse as check-in message."""
        for pattern in self.CHECKIN_PATTERNS:
            if pattern.match(message):
                # Higher confidence for exact "Available" match
                confidence = 0.95 if "available" in message.lower() else 0.85
                return ParsedAttendance(
                    event_type=ParsedEventType.CHECKIN,
                    confidence=confidence,
                )
        return None

    def _try_checkout(self, message: str) -> Optional[ParsedAttendance]:
        """Try to parse as check-out message."""
        for pattern in self.CHECKOUT_PATTERNS:
            if pattern.match(message):
                # Higher confidence for exact "Signing Out" match
                confidence = 0.95 if "signing out" in message.lower() else 0.85
                return ParsedAttendance(
                    event_type=ParsedEventType.CHECKOUT,
                    confidence=confidence,
                )
        return None

    def _try_break_start(self, message: str) -> Optional[ParsedAttendance]:
        """Try to parse as break start message."""
        # Try main BRB pattern first
        match = self.BREAK_START_PATTERN.match(message)
        if match:
            reason = match.group("reason")
            return self._build_break_result(reason, message)

        # Try alternative patterns
        for pattern in self.BREAK_START_ALT_PATTERNS:
            match = pattern.match(message)
            if match:
                reason = match.groupdict().get("reason", "").strip() or None
                return self._build_break_result(reason, message)

        return None

    def _build_break_result(self, reason: Optional[str], message: str) -> ParsedAttendance:
        """Build break start result with reason analysis."""
        category = None
        duration = None
        urgency = "normal"

        if reason:
            reason = reason.strip()
            category = self._categorize_reason(reason)
            duration = self._extract_duration(reason)

            # Check for urgency
            if any(kw in reason.lower() for kw in self.EMERGENCY_KEYWORDS):
                urgency = "urgent"

        return ParsedAttendance(
            event_type=ParsedEventType.BREAK_START,
            confidence=0.95 if "brb" in message.lower() else 0.85,
            reason=reason,
            reason_category=category,
            expected_duration_minutes=duration,
            urgency=urgency,
        )

    def _try_break_end(self, message: str) -> Optional[ParsedAttendance]:
        """Try to parse as break end message."""
        for pattern in self.BREAK_END_PATTERNS:
            if pattern.match(message):
                confidence = 0.95 if message.lower().strip() == "back" else 0.85
                return ParsedAttendance(
                    event_type=ParsedEventType.BREAK_END,
                    confidence=confidence,
                )
        return None

    def _categorize_reason(self, reason: str) -> BreakReasonCategory:
        """Categorize a break reason."""
        reason_lower = reason.lower()

        if any(kw in reason_lower for kw in self.MEAL_KEYWORDS):
            return BreakReasonCategory.MEAL

        if any(kw in reason_lower for kw in self.PERSONAL_KEYWORDS):
            return BreakReasonCategory.PERSONAL

        if any(kw in reason_lower for kw in self.REST_KEYWORDS):
            return BreakReasonCategory.REST

        if any(kw in reason_lower for kw in self.MEETING_KEYWORDS):
            return BreakReasonCategory.MEETING

        if any(kw in reason_lower for kw in self.EMERGENCY_KEYWORDS):
            return BreakReasonCategory.EMERGENCY

        return BreakReasonCategory.OTHER

    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract expected duration in minutes from text."""
        for pattern in self.DURATION_PATTERNS:
            match = pattern.search(text)
            if match:
                value = int(match.group(1))
                # Check if it's hours
                if "hour" in pattern.pattern.lower() or "hr" in pattern.pattern.lower():
                    return value * 60
                # Assume minutes, but cap at reasonable values
                if value <= 480:  # Max 8 hours
                    return value
        return None
